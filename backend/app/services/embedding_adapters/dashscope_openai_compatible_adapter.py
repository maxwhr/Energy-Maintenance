from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import threading
import time
from typing import Any

import httpx

from app.services.embedding_adapters.base import EmbeddingAdapter, EmbeddingAdapterError, EmbeddingResult

logger = logging.getLogger(__name__)


class DashScopeOpenAICompatibleEmbeddingAdapter(EmbeddingAdapter):
    """DashScope compatible adapter with bounded concurrency and safe telemetry."""

    provider_code = "dashscope_openai_compatible"
    _shared_sync_client: httpx.Client | None = None
    _shared_client_lock = threading.Lock()
    _sync_semaphore = threading.BoundedSemaphore(8)

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "text-embedding-v4",
        dimension: int = 1024,
        embeddings_path: str = "/embeddings",
        encoding_format: str = "float",
        timeout_seconds: int = 60,
        max_retries: int = 4,
        retry_base_seconds: float = 1.0,
        max_concurrency: int = 2,
        allow_real_api: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.model = model or ""
        self.dimension = int(dimension or 0)
        self.embeddings_path = embeddings_path if embeddings_path.startswith("/") else f"/{embeddings_path}"
        self.encoding_format = encoding_format
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_base_seconds = max(0.01, retry_base_seconds)
        self.allow_real_api = allow_real_api
        self._semaphore = asyncio.Semaphore(max(1, min(2, max_concurrency)))
        self._client = client

    def check_status(self) -> dict:
        configured = bool(self.base_url and self.api_key and self.model and self.dimension == 1024)
        return {
            "provider": self.provider_code,
            "model": self.model or None,
            "dimension": self.dimension,
            "configured": configured,
            "status": "available" if configured and self.allow_real_api else "blocked",
            "blocked_reason": None if configured and self.allow_real_api else "real embedding API is disabled or not configured",
        }

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if self._client is None:
            return self._embed_texts_sync(texts)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.aembed_texts(texts))
        raise EmbeddingAdapterError("sync embedding call cannot run inside an active event loop; use aembed_texts")

    async def aembed_texts(self, texts: list[str]) -> EmbeddingResult:
        if self._client is None:
            return await asyncio.to_thread(self._embed_texts_sync, texts)
        if not self.allow_real_api:
            raise EmbeddingAdapterError("real embedding API is disabled; explicit Task 25B approval is required")
        if not (self.base_url and self.api_key and self.model and self.dimension == 1024):
            raise EmbeddingAdapterError("DashScope embedding configuration is incomplete or dimension is not 1024")
        if not texts or len(texts) > 10:
            raise EmbeddingAdapterError("DashScope text-embedding-v4 accepts 1 to 10 inputs per batch")

        payload = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimension,
            "encoding_format": self.encoding_format,
        }
        started = time.perf_counter()
        retries = 0
        response: httpx.Response | None = None
        async with self._semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    client = self._client or httpx.AsyncClient(timeout=self.timeout_seconds)
                    try:
                        response = await client.post(
                            f"{self.base_url}{self.embeddings_path}",
                            headers={"Authorization": f"Bearer {self.api_key}"},
                            json=payload,
                        )
                    finally:
                        if self._client is None:
                            await client.aclose()
                    if response.status_code < 400:
                        break
                    if response.status_code != 429 and response.status_code < 500:
                        raise EmbeddingAdapterError(f"embedding API HTTP error: {response.status_code}")
                    if attempt >= self.max_retries:
                        raise EmbeddingAdapterError(f"embedding API retry exhausted: HTTP {response.status_code}")
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt >= self.max_retries:
                        raise EmbeddingAdapterError(f"embedding API transport error: {type(exc).__name__}") from exc
                retries += 1
                await asyncio.sleep(self.retry_base_seconds * (2**attempt))

        if response is None:
            raise EmbeddingAdapterError("embedding API returned no response")
        try:
            body = response.json()
        except ValueError as exc:
            raise EmbeddingAdapterError("embedding API returned invalid JSON") from exc
        vectors = self._extract_vectors(body, expected_count=len(texts), expected_dimension=self.dimension)
        request_id = response.headers.get("x-request-id") or body.get("request_id") or body.get("id")
        usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
        telemetry = {
            "request_id": request_id,
            "model": self.model,
            "dimension": self.dimension,
            "usage": usage,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "retries": retries,
            "input_count": len(texts),
            "character_count": sum(len(text) for text in texts),
            "input_hashes": [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts],
            "external_api_called": True,
        }
        logger.info("embedding_request_completed %s", telemetry)
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_code,
            model=self.model,
            dimension=self.dimension,
            metadata=telemetry,
        )

    def _embed_texts_sync(self, texts: list[str]) -> EmbeddingResult:
        if not self.allow_real_api:
            raise EmbeddingAdapterError("real embedding API is disabled; explicit Task 25B approval is required")
        if not (self.base_url and self.api_key and self.model and self.dimension == 1024):
            raise EmbeddingAdapterError("DashScope embedding configuration is incomplete or dimension is not 1024")
        if not texts or len(texts) > 10:
            raise EmbeddingAdapterError("DashScope text-embedding-v4 accepts 1 to 10 inputs per batch")
        payload = {
            "model": self.model, "input": texts, "dimensions": self.dimension,
            "encoding_format": self.encoding_format,
        }
        client = self._sync_client(self.timeout_seconds)
        started = time.perf_counter()
        retries = 0
        response: httpx.Response | None = None
        with self._sync_semaphore:
            for attempt in range(self.max_retries + 1):
                try:
                    response = client.post(
                        f"{self.base_url}{self.embeddings_path}",
                        headers={"Authorization": f"Bearer {self.api_key}"}, json=payload,
                    )
                    if response.status_code < 400:
                        break
                    if response.status_code != 429 and response.status_code < 500:
                        raise EmbeddingAdapterError(f"embedding API HTTP error: {response.status_code}")
                    if attempt >= self.max_retries:
                        raise EmbeddingAdapterError(f"embedding API retry exhausted: HTTP {response.status_code}")
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempt >= self.max_retries:
                        raise EmbeddingAdapterError(f"embedding API transport error: {type(exc).__name__}") from exc
                retries += 1
                time.sleep(self.retry_base_seconds * (2**attempt))
        if response is None:
            raise EmbeddingAdapterError("embedding API returned no response")
        try:
            body = response.json()
        except ValueError as exc:
            raise EmbeddingAdapterError("embedding API returned invalid JSON") from exc
        vectors = self._extract_vectors(body, expected_count=len(texts), expected_dimension=self.dimension)
        telemetry = {
            "request_id": response.headers.get("x-request-id") or body.get("request_id") or body.get("id"),
            "model": self.model, "dimension": self.dimension,
            "usage": body.get("usage") if isinstance(body.get("usage"), dict) else {},
            "latency_ms": round((time.perf_counter() - started) * 1000, 3), "retries": retries,
            "input_count": len(texts), "character_count": sum(len(text) for text in texts),
            "input_hashes": [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts],
            "external_api_called": True, "connection_reused": True,
        }
        logger.info("embedding_request_completed %s", telemetry)
        return EmbeddingResult(
            vectors=vectors, provider=self.provider_code, model=self.model,
            dimension=self.dimension, metadata=telemetry,
        )

    @classmethod
    def _sync_client(cls, timeout_seconds: int) -> httpx.Client:
        with cls._shared_client_lock:
            if cls._shared_sync_client is None or cls._shared_sync_client.is_closed:
                cls._shared_sync_client = httpx.Client(
                    timeout=timeout_seconds,
                    limits=httpx.Limits(max_connections=8, max_keepalive_connections=8, keepalive_expiry=120),
                )
            return cls._shared_sync_client

    @staticmethod
    def _extract_vectors(data: dict[str, Any], *, expected_count: int, expected_dimension: int) -> list[list[float]]:
        items = data.get("data")
        if not isinstance(items, list):
            raise EmbeddingAdapterError("embedding API returned unsupported response structure")
        ordered: list[tuple[int, list[float]]] = []
        for fallback_index, item in enumerate(items):
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise EmbeddingAdapterError("embedding API returned an invalid vector item")
            index = item.get("index", fallback_index)
            if not isinstance(index, int):
                raise EmbeddingAdapterError("embedding API returned an invalid vector index")
            try:
                vector = [float(value) for value in item["embedding"]]
            except (TypeError, ValueError) as exc:
                raise EmbeddingAdapterError("embedding vector contains a non-numeric value") from exc
            if len(vector) != expected_dimension:
                raise EmbeddingAdapterError("embedding dimension mismatch")
            if not all(math.isfinite(value) for value in vector):
                raise EmbeddingAdapterError("embedding vector contains NaN or Infinity")
            ordered.append((index, vector))
        ordered.sort(key=lambda pair: pair[0])
        if [item[0] for item in ordered] != list(range(expected_count)):
            raise EmbeddingAdapterError("embedding response order/index mismatch")
        return [item[1] for item in ordered]
