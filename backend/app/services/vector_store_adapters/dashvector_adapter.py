from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.services.vector_store_adapters.base import (
    VectorRecord,
    VectorSearchHit,
    VectorStoreAdapter,
    VectorStoreAdapterError,
)


class DashVectorAdapter(VectorStoreAdapter):
    backend_code = "dashvector"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        collection_name: str,
        namespace: str | None,
        dimension: int,
        metric: str = "cosine",
        timeout_seconds: int = 60,
        allow_real_api: bool = False,
    ):
        self.endpoint = (endpoint or "").rstrip("/")
        self.api_key = api_key or ""
        self.collection_name = collection_name
        self.namespace = namespace or "default"
        self.dimension = int(dimension or 0)
        self.metric = metric
        self.timeout_seconds = timeout_seconds
        self.allow_real_api = allow_real_api

    def check_status(self) -> dict:
        configured = bool(self.endpoint and self.api_key and self.collection_name and self.dimension > 0)
        return {
            "backend": self.backend_code,
            "configured": configured,
            "status": "available" if configured and self.allow_real_api else "blocked",
            "blocked_reason": None if configured and self.allow_real_api else "DashVector real call is disabled or not configured",
            "collection_name": self.collection_name,
            "namespace": self.namespace,
            "dimension": self.dimension,
            "external_api_called": False,
        }

    def ensure_collection(self, *, dimension: int) -> None:
        if not self.allow_real_api:
            raise VectorStoreAdapterError("real DashVector API is disabled; use fake_in_memory for local tests")
        if dimension != self.dimension:
            raise VectorStoreAdapterError("DashVector dimension mismatch")
        try:
            self._request("GET", f"/v1/collections/{self.collection_name}")
        except VectorStoreAdapterError as exc:
            if "HTTP error: 404" not in str(exc):
                raise
            self._request(
                "POST",
                "/v1/collections",
                payload={
                    "name": self.collection_name,
                    "dimension": self.dimension,
                    "metric": self.metric,
                    "fields_schema": {
                        "chunk_id": "STRING",
                        "document_id": "STRING",
                        "document_title": "STRING",
                        "manufacturer": "STRING",
                        "product_series": "STRING",
                        "device_type": "STRING",
                        "document_type": "STRING",
                        "review_status": "STRING",
                        "parse_status": "STRING",
                        "status": "STRING",
                    },
                },
            )

    def upsert_vectors(self, records: list[VectorRecord]) -> None:
        if not self.allow_real_api:
            raise VectorStoreAdapterError("real DashVector API is disabled; use fake_in_memory for local tests")
        payload = {
            "docs": [
                {
                    "id": record.vector_id,
                    "vector": record.vector,
                    "fields": self._safe_metadata(record.metadata),
                }
                for record in records
            ]
        }
        self._request("POST", f"/v1/collections/{self.collection_name}/docs", payload=payload)

    def query_vectors(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[VectorSearchHit]:
        if not self.allow_real_api:
            raise VectorStoreAdapterError("real DashVector API is disabled; use fake_in_memory for local tests")
        payload: dict[str, Any] = {
            "vector": vector,
            "topk": top_k,
            "include_vector": False,
            "output_fields": ["chunk_id", "document_id", "document_title", "chunk_index"],
        }
        if filters:
            payload["filter"] = self._filter_expression(filters)
        data = self._request("POST", f"/v1/collections/{self.collection_name}/query", payload=payload)
        docs = data.get("output", {}).get("docs") or data.get("docs") or []
        hits: list[VectorSearchHit] = []
        for item in docs:
            fields = item.get("fields") or item.get("metadata") or {}
            hits.append(
                VectorSearchHit(
                    vector_id=str(item.get("id") or fields.get("vector_id") or ""),
                    score=float(item.get("score") or item.get("similarity") or 0),
                    metadata=fields,
                )
            )
        return hits

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        if not self.endpoint or not self.api_key:
            raise VectorStoreAdapterError("DashVector endpoint or API key is not configured")
        url = f"{self.endpoint}{path}"
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "DashVector-Auth-Token": self.api_key,
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise VectorStoreAdapterError(f"DashVector HTTP error: {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise VectorStoreAdapterError(f"DashVector network error: {exc.reason}") from exc
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise VectorStoreAdapterError("DashVector returned invalid JSON") from exc

    @staticmethod
    def _safe_metadata(metadata: dict) -> dict:
        return {key: value for key, value in metadata.items() if key not in {"api_key", "authorization", "vector"}}

    @staticmethod
    def _filter_expression(filters: dict) -> str:
        parts = []
        for key, value in filters.items():
            if value in (None, "", "other"):
                continue
            parts.append(f"{key} = '{str(value).replace(chr(39), chr(39) + chr(39))}'")
        return " and ".join(parts)
