from __future__ import annotations

import hashlib
import json
import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx

from app.core.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class Qwen3RerankItem:
    index: int
    relevance_score: float


@dataclass(frozen=True, slots=True)
class Qwen3RerankProviderResult:
    success: bool
    status: str
    model: str
    results: tuple[Qwen3RerankItem, ...] = ()
    request_id_hash: str | None = None
    latency_ms: float = 0.0
    cache_hit: bool = False
    circuit_breaker_state: str = "CLOSED"
    fallback_reason: str | None = None


class _SuccessCache:
    def __init__(self, *, max_entries: int, ttl_seconds: int) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._values: OrderedDict[str, tuple[float, Qwen3RerankProviderResult]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Qwen3RerankProviderResult | None:
        now = time.monotonic()
        with self._lock:
            value = self._values.get(key)
            if value is None:
                return None
            expires_at, result = value
            if expires_at <= now:
                self._values.pop(key, None)
                return None
            self._values.move_to_end(key)
            return Qwen3RerankProviderResult(
                success=result.success,
                status=result.status,
                model=result.model,
                results=result.results,
                request_id_hash=result.request_id_hash,
                latency_ms=0.0,
                cache_hit=True,
                circuit_breaker_state=result.circuit_breaker_state,
                fallback_reason=None,
            )

    def set(self, key: str, result: Qwen3RerankProviderResult) -> None:
        if not result.success:
            return
        with self._lock:
            self._values[key] = (time.monotonic() + self.ttl_seconds, result)
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)


class _CircuitBreaker:
    def __init__(self, *, threshold: int, cooldown_seconds: int) -> None:
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.failures = 0
        self.opened_at: float | None = None
        self._lock = Lock()

    def state(self) -> str:
        with self._lock:
            if self.opened_at is None:
                return "CLOSED"
            if time.monotonic() - self.opened_at >= self.cooldown_seconds:
                return "HALF_OPEN"
            return "OPEN"

    def allow(self) -> bool:
        state = self.state()
        return state != "OPEN"

    def success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()


class Qwen3RerankAdapter:
    """DashScope workspace rerank adapter with sanitized, lossless failure semantics."""

    _shared_clients: dict[str, httpx.AsyncClient] = {}
    _shared_clients_lock = Lock()

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._injected_client = client
        self.cache = _SuccessCache(
            max_entries=self.settings.DASHSCOPE_RERANK_CACHE_MAX_ENTRIES,
            ttl_seconds=self.settings.DASHSCOPE_RERANK_CACHE_TTL_SECONDS,
        )
        self.breaker = _CircuitBreaker(
            threshold=self.settings.DASHSCOPE_RERANK_CIRCUIT_FAILURE_THRESHOLD,
            cooldown_seconds=self.settings.DASHSCOPE_RERANK_CIRCUIT_COOLDOWN_SECONDS,
        )

    async def rerank(
        self,
        *,
        query: str,
        documents: list[str],
        top_n: int,
        instruct: str,
        allow_real_api: bool,
        request_id: str | None = None,
    ) -> Qwen3RerankProviderResult:
        model = self.settings.DASHSCOPE_RERANK_MODEL or self.settings.RAG_DEDICATED_RERANK_MODEL
        configuration_error = self._configuration_error()
        if configuration_error:
            return self._failure(configuration_error, model, request_id=request_id)
        if not allow_real_api or not self.settings.TASK25B_ALLOW_REAL_API:
            return self._failure("QWEN3_RERANK_REAL_API_NOT_ALLOWED", model, request_id=request_id)
        if not documents:
            return self._failure("QWEN3_RERANK_EMPTY_DOCUMENTS", model, request_id=request_id)
        if not self.breaker.allow():
            return self._failure(
                "QWEN3_RERANK_CIRCUIT_OPEN", model, request_id=request_id, circuit_state="OPEN"
            )

        limited_documents = documents[: self.settings.DASHSCOPE_RERANK_MAX_DOCUMENTS]
        bounded_top_n = min(max(1, top_n), len(limited_documents), self.settings.DASHSCOPE_RERANK_TOP_N)
        cache_key = self._cache_key(model, instruct, query, limited_documents, bounded_top_n)
        if self.settings.DASHSCOPE_RERANK_CACHE_ENABLED:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        url = self._url()
        payload = {
            "model": model,
            "query": query,
            "documents": limited_documents,
            "top_n": bounded_top_n,
            "instruct": instruct,
        }
        started = time.perf_counter()
        try:
            response = await self._client().post(
                url,
                headers={"Authorization": f"Bearer {self.settings.DASHSCOPE_API_KEY}"},
                json=payload,
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            if response.status_code == 429:
                raise _ProviderFailure("QWEN3_RERANK_RATE_LIMITED")
            if response.status_code >= 500:
                raise _ProviderFailure("QWEN3_RERANK_PROVIDER_5XX")
            if response.status_code >= 400:
                raise _ProviderFailure("QWEN3_RERANK_PROVIDER_REJECTED")
            try:
                body = response.json()
            except (ValueError, json.JSONDecodeError) as exc:
                raise _ProviderFailure("QWEN3_RERANK_INVALID_RESPONSE") from exc
            parsed = self._parse_results(body, document_count=len(limited_documents), top_n=bounded_top_n)
            provider_request_id = str(
                body.get("request_id") or response.headers.get("x-request-id") or request_id or cache_key
            )
            result = Qwen3RerankProviderResult(
                success=True,
                status="QWEN3_RERANK_SUCCESS",
                model=model,
                results=tuple(parsed),
                request_id_hash=self._hash(provider_request_id),
                latency_ms=latency_ms,
                cache_hit=False,
                circuit_breaker_state="CLOSED",
            )
            self.breaker.success()
            if self.settings.DASHSCOPE_RERANK_CACHE_ENABLED:
                self.cache.set(cache_key, result)
            return result
        except httpx.TimeoutException:
            return self._provider_failure("QWEN3_RERANK_TIMEOUT", model, request_id, started)
        except httpx.RequestError:
            return self._provider_failure("QWEN3_RERANK_UNAVAILABLE", model, request_id, started)
        except _ProviderFailure as exc:
            return self._provider_failure(exc.reason_code, model, request_id, started)
        except Exception:  # noqa: BLE001 - never expose provider response or credentials.
            return self._provider_failure("QWEN3_RERANK_PROVIDER_ERROR", model, request_id, started)

    def _configuration_error(self) -> str | None:
        if not self.settings.DASHSCOPE_API_KEY.strip():
            return "QWEN3_RERANK_CONFIG_MISSING"
        if not self.settings.DASHSCOPE_RERANK_BASE_URL.strip():
            return "QWEN3_RERANK_CONFIG_MISSING"
        if not self.settings.DASHSCOPE_RERANK_ENDPOINT.strip():
            return "QWEN3_RERANK_CONFIG_MISSING"
        if not (self.settings.DASHSCOPE_RERANK_MODEL or self.settings.RAG_DEDICATED_RERANK_MODEL).strip():
            return "QWEN3_RERANK_CONFIG_MISSING"
        if not self.settings.DASHSCOPE_RERANK_ENABLED or not self.settings.RAG_DEDICATED_RERANK_ENABLED:
            return "QWEN3_RERANK_DISABLED"
        if self.settings.RAG_DEDICATED_RERANK_PROVIDER.lower() != "dashscope":
            return "QWEN3_RERANK_PROVIDER_UNSUPPORTED"
        return None

    def _client(self) -> httpx.AsyncClient:
        if self._injected_client is not None:
            return self._injected_client
        key = self.settings.DASHSCOPE_RERANK_BASE_URL.rstrip("/")
        with self._shared_clients_lock:
            if key not in self._shared_clients:
                total = self.settings.DASHSCOPE_RERANK_TIMEOUT_SECONDS
                self._shared_clients[key] = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=min(2.0, total),
                        read=total,
                        write=min(2.0, total),
                        pool=min(1.0, total),
                    ),
                    limits=httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0),
                )
            return self._shared_clients[key]

    def _url(self) -> str:
        return (
            self.settings.DASHSCOPE_RERANK_BASE_URL.rstrip("/")
            + "/"
            + self.settings.DASHSCOPE_RERANK_ENDPOINT.strip("/")
        )

    @staticmethod
    def _parse_results(body: dict[str, Any], *, document_count: int, top_n: int) -> list[Qwen3RerankItem]:
        raw = body.get("results")
        if raw is None and isinstance(body.get("output"), dict):
            raw = body["output"].get("results")
        if not isinstance(raw, list) or not raw:
            raise _ProviderFailure("QWEN3_RERANK_INVALID_RESPONSE")
        if len(raw) > top_n:
            raise _ProviderFailure("QWEN3_RERANK_INVALID_RESPONSE")
        parsed: list[tuple[int, Qwen3RerankItem]] = []
        seen: set[int] = set()
        for position, item in enumerate(raw):
            if not isinstance(item, dict):
                raise _ProviderFailure("QWEN3_RERANK_INVALID_RESPONSE")
            index = item.get("index")
            score = item.get("relevance_score")
            if not isinstance(index, int) or index < 0 or index >= document_count or index in seen:
                raise _ProviderFailure("QWEN3_RERANK_INVALID_RESPONSE")
            if not isinstance(score, (int, float)) or not math.isfinite(float(score)):
                raise _ProviderFailure("QWEN3_RERANK_INVALID_RESPONSE")
            seen.add(index)
            parsed.append((position, Qwen3RerankItem(index=index, relevance_score=float(score))))
        parsed.sort(key=lambda value: (-value[1].relevance_score, value[0]))
        return [value[1] for value in parsed]

    @classmethod
    def _cache_key(cls, model: str, instruct: str, query: str, documents: list[str], top_n: int) -> str:
        hashes = [cls._hash(document) for document in documents]
        candidate_set_hash = cls._hash("|".join(sorted(hashes)))
        payload = {
            "model": model,
            "instruct_hash": cls._hash(instruct),
            "query_hash": cls._hash(query),
            "candidate_set_hash": candidate_set_hash,
            "rerank_text_hashes": hashes,
            "top_n": top_n,
        }
        return cls._hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))

    def _provider_failure(self, reason: str, model: str, request_id: str | None, started: float) -> Qwen3RerankProviderResult:
        self.breaker.failure()
        return self._failure(
            reason,
            model,
            request_id=request_id,
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            circuit_state=self.breaker.state(),
        )

    @classmethod
    def _failure(
        cls,
        reason: str,
        model: str,
        *,
        request_id: str | None,
        latency_ms: float = 0.0,
        circuit_state: str = "CLOSED",
    ) -> Qwen3RerankProviderResult:
        return Qwen3RerankProviderResult(
            success=False,
            status=reason,
            model=model,
            request_id_hash=cls._hash(request_id) if request_id else None,
            latency_ms=latency_ms,
            circuit_breaker_state=circuit_state,
            fallback_reason=reason,
        )

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _ProviderFailure(RuntimeError):
    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
