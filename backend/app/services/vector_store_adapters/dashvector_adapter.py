from __future__ import annotations

import copy
import json
import hashlib
import math
import random
import threading
import time
from typing import Any
from urllib.parse import quote

import httpx

from app.services.vector_store_adapters.base import (
    VectorRecord,
    VectorSearchHit,
    VectorStoreAdapter,
    VectorStoreAdapterError,
)


class DashVectorAdapter(VectorStoreAdapter):
    backend_code = "dashvector"
    _shared_clients: dict[str, httpx.Client] = {}
    _client_lock = threading.Lock()
    # Per-request work remains bounded by RAG_MAX_QUERY_VARIANT_CONCURRENCY and
    # RAG_MAX_VECTOR_CONCURRENCY. This process-wide cap prevents unbounded load
    # while allowing the required 20-request concurrency level to make progress.
    _request_semaphore = threading.BoundedSemaphore(24)
    _query_cache_lock = threading.Lock()
    _query_cache: dict[str, tuple[float, dict]] = {}
    _query_inflight: dict[str, threading.Event] = {}
    # Long enough to cover a burst of duplicate UI/service requests, but short
    # enough that vector collection changes are observed without a process
    # restart. Database scope/status validation still runs on every request.
    _query_cache_ttl_seconds = 60.0
    _query_cache_max_entries = 256
    _query_cache_hits = 0
    _query_network_requests = 0

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        collection_name: str,
        namespace: str | None,
        dimension: int,
        metric: str = "cosine",
        dtype: str = "float",
        timeout_seconds: int = 60,
        upsert_batch_size: int = 50,
        allow_real_api: bool = False,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        index_version: str | None = None,
        retrieval_config_version: str | None = None,
        max_query_retries: int = 1,
    ):
        self.endpoint = (endpoint or "").rstrip("/")
        self.api_key = api_key or ""
        self.collection_name = collection_name
        self.namespace = namespace or "default"
        self.dimension = int(dimension or 0)
        self.metric = metric.lower()
        self.dtype = dtype.lower()
        self.timeout_seconds = timeout_seconds
        self.upsert_batch_size = max(1, min(100, upsert_batch_size))
        self.allow_real_api = allow_real_api
        self.embedding_provider = embedding_provider or "unknown"
        self.embedding_model = embedding_model or "unknown"
        self.index_version = index_version or "unknown"
        self.retrieval_config_version = retrieval_config_version or "unknown"
        self.max_query_retries = max(0, min(1, int(max_query_retries)))
        self.last_request_latency_ms = 0.0
        self.last_retries = 0

    def check_status(self) -> dict:
        configured = bool(
            self.endpoint.startswith("https://") and self.api_key and self.collection_name
            and self.dimension == 1024 and self.metric == "cosine" and self.dtype == "float"
        )
        return {
            "backend": self.backend_code,
            "configured": configured,
            "status": "available" if configured and self.allow_real_api else "blocked",
            "blocked_reason": None if configured and self.allow_real_api else "DashVector real call is disabled or not configured",
            "collection_name": self.collection_name,
            "namespace": self.namespace,
            "dimension": self.dimension,
            "metric": self.metric,
            "dtype": self.dtype,
            "external_api_called": False,
        }

    def ensure_collection(self, *, dimension: int) -> str:
        self._require_real()
        if dimension != self.dimension:
            raise VectorStoreAdapterError("DashVector dimension mismatch")
        try:
            data = self._request("GET", f"/v1/collections/{self.collection_name}")
        except VectorStoreAdapterError as exc:
            if "HTTP error: 404" not in str(exc) and "error code: -2021" not in str(exc):
                raise
            self._create_collection()
            return self.collection_name
        output = data.get("output") or {}
        actual = {
            "dimension": int(output.get("dimension") or 0),
            "metric": str(output.get("metric") or "").lower(),
            "dtype": str(output.get("dtype") or "").lower(),
        }
        expected = {"dimension": self.dimension, "metric": self.metric, "dtype": self.dtype}
        if actual != expected:
            raise VectorStoreAdapterError(
                "existing DashVector collection schema mismatch; configure a new versioned collection name"
            )
        return self.collection_name

    def _create_collection(self) -> None:
        self._request(
            "POST",
            "/v1/collections",
            payload={
                "name": self.collection_name,
                "dimension": self.dimension,
                "metric": self.metric,
                "dtype": self.dtype.upper(),
                "fields_schema": {
                    "chunk_id": "STRING", "document_id": "STRING", "document_title": "STRING",
                    "manufacturer": "STRING", "product_series": "STRING", "device_type": "STRING",
                    "document_type": "STRING", "review_status": "STRING", "parse_status": "STRING",
                    "status": "STRING", "content_hash": "STRING", "embedding_model": "STRING",
                    "embedding_dimension": "INT", "embedding_version": "STRING", "device_model": "STRING",
                    "fault_codes": "STRING", "section_path": "STRING", "page_number": "INT",
                    "object_type": "STRING", "media_id": "STRING",
                },
            },
        )

    def ensure_partition(self, partition_name: str) -> str:
        self._require_real()
        if not partition_name or partition_name == "default":
            return "default"
        data = self._request("GET", f"/v1/collections/{self.collection_name}/partitions")
        output = data.get("output") or []
        names = output if isinstance(output, list) else output.get("partitions") or []
        if partition_name not in {str(item) for item in names}:
            self._request(
                "POST", f"/v1/collections/{self.collection_name}/partitions",
                payload={"name": partition_name},
            )
        return partition_name

    def fetch_documents(self, vector_ids: list[str]) -> dict[str, dict]:
        self._require_real()
        if not vector_ids:
            return {}
        ids = quote(",".join(vector_ids), safe=",")
        partition = quote(self.namespace, safe="")
        data = self._request(
            "GET", f"/v1/collections/{self.collection_name}/docs?ids={ids}&partition={partition}"
        )
        output = data.get("output") or {}
        if not isinstance(output, dict):
            return {}
        return {
            str(key): {"id": str((item or {}).get("id") or key), "fields": (item or {}).get("fields") or {}}
            for key, item in output.items() if item
        }

    def collection_stats(self) -> dict:
        self._require_real()
        data = self._request("GET", f"/v1/collections/{self.collection_name}/stats")
        output = data.get("output") or {}
        return output if isinstance(output, dict) else {}

    def upsert_vectors(self, records: list[VectorRecord]) -> None:
        self._require_real()
        for record in records:
            if len(record.vector) != self.dimension or not all(math.isfinite(value) for value in record.vector):
                raise VectorStoreAdapterError("vector dimension or numeric value is invalid")
        for offset in range(0, len(records), self.upsert_batch_size):
            batch = records[offset : offset + self.upsert_batch_size]
            self._request(
                "POST",
                f"/v1/collections/{self.collection_name}/docs/upsert",
                payload={
                    "docs": [
                        {"id": record.vector_id, "vector": record.vector, "fields": self._safe_metadata(record.metadata)}
                        for record in batch
                    ],
                    "partition": self.namespace,
                },
            )

    def delete_vectors(self, vector_ids: list[str]) -> None:
        self._require_real()
        if vector_ids:
            self._request(
                "DELETE", f"/v1/collections/{self.collection_name}/docs",
                payload={"ids": vector_ids, "partition": self.namespace},
            )

    def query_vectors(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict | None = None,
        request_context: dict[str, Any] | None = None,
    ) -> list[VectorSearchHit]:
        self._require_real()
        if len(vector) != self.dimension or not all(math.isfinite(value) for value in vector):
            raise VectorStoreAdapterError("query vector dimension or numeric value is invalid")
        payload: dict[str, Any] = {
            "vector": vector,
            "topk": max(1, min(50, top_k)),
            "include_vector": False,
            "partition": self.namespace,
            "output_fields": [
                "chunk_id", "document_id", "document_title", "chunk_index", "manufacturer",
                "product_series", "device_type", "document_type", "review_status", "parse_status",
                "status", "content_hash", "embedding_model", "embedding_dimension", "embedding_version",
                "device_model", "fault_codes", "section_path", "page_number", "object_type",
                "media_id", "semantic_unit_id", "source_chunk_ids_hash", "anchor_type",
                "representation_version", "normalized_language", "approval_mode",
                "approved_for_pilot", "current_version", "quality_status",
            ],
        }
        if filters:
            payload["filter"] = self._filter_expression(filters)
        data = self._coalesced_query_request(payload, request_context=request_context)
        output = data.get("output")
        docs = output if isinstance(output, list) else (output or {}).get("docs") or data.get("docs") or []
        hits: list[VectorSearchHit] = []
        for item in docs:
            fields = item.get("fields") or item.get("metadata") or {}
            raw = float(item.get("score") if item.get("score") is not None else item.get("similarity") or 0)
            normalized = self.normalize_score(raw, metric=self.metric)
            hits.append(VectorSearchHit(
                vector_id=str(item.get("id") or fields.get("vector_id") or ""),
                score=normalized,
                raw_score=raw,
                normalized_score=normalized,
                metadata={**fields, "vector_raw_score": raw, "vector_score": normalized},
            ))
        hits.sort(key=lambda item: (-round(item.score, 8), item.vector_id))
        return hits

    def _coalescing_key_components(
        self,
        payload: dict[str, Any],
        *,
        request_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = dict(request_context or {})
        vector = payload.get("vector") or []
        output_fields = list(payload.get("output_fields") or [])
        return {
            "provider": self.backend_code,
            "endpoint_hash": hashlib.sha256(self.endpoint.encode("utf-8")).hexdigest(),
            "collection": self.collection_name,
            "partition": str(payload.get("partition") or self.namespace),
            "operation": str(context.get("operation") or "vector_query"),
            "embedding_provider": str(context.get("embedding_provider") or self.embedding_provider),
            "embedding_model": str(context.get("embedding_model") or self.embedding_model),
            "embedding_dimension": int(context.get("embedding_dimension") or self.dimension),
            "vector_content_hash": hashlib.sha256(
                json.dumps(vector, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ).hexdigest(),
            "top_k": int(payload.get("topk") or 0),
            "filter_expression_hash": hashlib.sha256(
                str(payload.get("filter") or "").encode("utf-8")
            ).hexdigest(),
            "score_threshold": context.get("score_threshold"),
            "metadata_output_fields": output_fields,
            "metadata_output_fields_hash": hashlib.sha256(
                json.dumps(output_fields, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "namespace": self.namespace,
            "distance_metric": self.metric,
            "query_mode": str(context.get("query_mode") or "raw_vector"),
            "index_version": str(context.get("index_version") or self.index_version),
            "retrieval_config_version": str(
                context.get("retrieval_config_version") or self.retrieval_config_version
            ),
            "scope_fingerprint": str(context.get("scope_fingerprint") or "provider_raw_unscoped"),
        }

    def _coalescing_cache_key(
        self,
        payload: dict[str, Any],
        *,
        request_context: dict[str, Any] | None = None,
    ) -> str:
        return hashlib.sha256(
            json.dumps(
                self._coalescing_key_components(payload, request_context=request_context),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _is_complete_query_response(value: dict[str, Any]) -> bool:
        if value.get("partial") is True or value.get("is_complete") is False:
            return False
        status = str(value.get("status") or "").casefold()
        return status not in {"partial", "incomplete", "cancelled"}

    def _coalesced_query_request(
        self,
        payload: dict[str, Any],
        *,
        request_context: dict[str, Any] | None = None,
    ) -> dict:
        """Coalesce identical short-lived vector reads without caching content.

        The key contains every provider request and retrieval-context dimension
        that can affect raw results. Cached data contains provider
        IDs/scores/metadata only; every caller still performs its own database
        scope, approval and source hydration checks.
        """
        cache_key = self._coalescing_cache_key(payload, request_context=request_context)
        while True:
            now = time.monotonic()
            owner = False
            with self._query_cache_lock:
                cached = self._query_cache.get(cache_key)
                if cached and cached[0] > now:
                    self.__class__._query_cache_hits += 1
                    self.last_request_latency_ms = 0.0
                    self.last_retries = 0
                    return copy.deepcopy(cached[1])
                if cached:
                    self._query_cache.pop(cache_key, None)
                event = self._query_inflight.get(cache_key)
                if event is None:
                    event = threading.Event()
                    self._query_inflight[cache_key] = event
                    owner = True
            if owner:
                break
            if not event.wait(timeout=max(1.0, float(self.timeout_seconds))):
                raise VectorStoreAdapterError("DashVector coalesced query wait timeout")

        try:
            with self._query_cache_lock:
                self.__class__._query_network_requests += 1
            result = self._request(
                "POST", f"/v1/collections/{self.collection_name}/query", payload=payload
            )
            if self._is_complete_query_response(result):
                with self._query_cache_lock:
                    now = time.monotonic()
                    expired = [key for key, value in self._query_cache.items() if value[0] <= now]
                    for key in expired:
                        self._query_cache.pop(key, None)
                    if len(self._query_cache) >= self._query_cache_max_entries:
                        oldest = min(self._query_cache, key=lambda key: self._query_cache[key][0])
                        self._query_cache.pop(oldest, None)
                    self._query_cache[cache_key] = (
                        now + self._query_cache_ttl_seconds,
                        copy.deepcopy(result),
                    )
            return copy.deepcopy(result)
        finally:
            if owner:
                with self._query_cache_lock:
                    self._query_inflight.pop(cache_key, None)
                    event.set()

    @classmethod
    def query_coalescing_snapshot(cls) -> dict[str, int]:
        with cls._query_cache_lock:
            return {
                "cache_hits": cls._query_cache_hits,
                "network_requests": cls._query_network_requests,
                "cache_entries": len(cls._query_cache),
                "inflight": len(cls._query_inflight),
            }

    @staticmethod
    def normalize_score(raw_score: float, *, metric: str) -> float:
        if not math.isfinite(raw_score):
            raise VectorStoreAdapterError("DashVector score is NaN or Infinity")
        if metric == "cosine":
            # DashVector exposes cosine distance in [0, 2]; lower is closer.
            return round(max(0.0, min(1.0, 1.0 - raw_score / 2.0)), 8)
        if metric == "euclidean":
            return round(1.0 / (1.0 + max(0.0, raw_score)), 8)
        return round(max(0.0, min(1.0, raw_score)), 8)

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        if not self.endpoint or not self.api_key:
            raise VectorStoreAdapterError("DashVector endpoint or API key is not configured")
        client = self._shared_client(self.endpoint, self.timeout_seconds)
        last_error: Exception | None = None
        started = time.perf_counter()
        retries = 0
        deadline = time.monotonic() + max(1.0, float(self.timeout_seconds))
        with self._request_semaphore:
            for attempt in range(self.max_query_retries + 1):
                try:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise httpx.ReadTimeout("DashVector request budget exhausted")
                    response = client.request(
                        method, f"{self.endpoint}{path}",
                        headers={"Content-Type": "application/json", "DashVector-Auth-Token": self.api_key},
                        json=payload,
                        timeout=remaining,
                    )
                    if response.status_code >= 400:
                        if response.status_code not in {429, 502, 503, 504}:
                            raise VectorStoreAdapterError(f"DashVector HTTP error: {response.status_code}")
                        last_error = httpx.HTTPStatusError("retryable DashVector response", request=response.request, response=response)
                    else:
                        try:
                            result = response.json() if response.content else {}
                        except ValueError as exc:
                            raise VectorStoreAdapterError("DashVector returned invalid JSON") from exc
                        if result.get("code") not in {None, 0}:
                            message = str(result.get("message") or result.get("msg") or "unspecified")[:240]
                            raise VectorStoreAdapterError(
                                f"DashVector API error code: {result.get('code')}; message: {message}"
                            )
                        self.last_request_latency_ms = round((time.perf_counter() - started) * 1000, 3)
                        self.last_retries = retries
                        return result
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_error = exc
                if attempt < self.max_query_retries and deadline - time.monotonic() > 0.05:
                    retries += 1
                    time.sleep(min(random.uniform(0.05, 0.15), max(0.0, deadline - time.monotonic())))
        self.last_request_latency_ms = round((time.perf_counter() - started) * 1000, 3)
        self.last_retries = retries
        if isinstance(last_error, httpx.HTTPStatusError):
            raise VectorStoreAdapterError(f"DashVector HTTP error: {last_error.response.status_code}") from last_error
        raise VectorStoreAdapterError("DashVector network retries exhausted") from last_error

    @classmethod
    def _shared_client(cls, endpoint: str, timeout_seconds: int) -> httpx.Client:
        with cls._client_lock:
            client = cls._shared_clients.get(endpoint)
            if client is None or client.is_closed:
                client = httpx.Client(
                    timeout=timeout_seconds,
                    limits=httpx.Limits(max_connections=24, max_keepalive_connections=24, keepalive_expiry=120),
                )
                cls._shared_clients[endpoint] = client
            return client

    def _require_real(self) -> None:
        if not self.allow_real_api:
            raise VectorStoreAdapterError("real DashVector API is disabled; explicit Task 25B approval is required")

    @staticmethod
    def _safe_metadata(metadata: dict) -> dict:
        blocked = {"api_key", "authorization", "vector", "file_path", "base64"}
        return {key: value for key, value in metadata.items() if key.lower() not in blocked and value is not None}

    @staticmethod
    def _filter_expression(filters: dict) -> str:
        parts = []
        allowed = {
            "manufacturer", "product_series", "device_type", "document_type", "review_status",
            "parse_status", "status", "object_type", "anchor_type", "normalized_language",
            "approval_mode", "quality_status", "approved_for_pilot", "current_version",
        }
        for key, value in filters.items():
            if key not in allowed or value in (None, "", "other"):
                continue
            parts.append(f"{key} = '{str(value).replace(chr(39), chr(39) + chr(39))}'")
        return " and ".join(parts)
