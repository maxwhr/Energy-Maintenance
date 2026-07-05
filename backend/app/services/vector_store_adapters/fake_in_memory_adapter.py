from __future__ import annotations

import math
from collections import defaultdict
from typing import ClassVar

from app.services.vector_store_adapters.base import VectorRecord, VectorSearchHit, VectorStoreAdapter


class FakeInMemoryVectorAdapter(VectorStoreAdapter):
    backend_code = "fake_in_memory"
    _collections: ClassVar[dict[str, dict[str, VectorRecord]]] = defaultdict(dict)

    def __init__(self, *, collection_name: str, namespace: str | None, dimension: int):
        self.collection_name = collection_name
        self.namespace = namespace or "default"
        self.dimension = dimension
        self.scope = f"{self.collection_name}:{self.namespace}:{self.dimension}"

    def check_status(self) -> dict:
        return {
            "backend": self.backend_code,
            "status": "available",
            "test_backend": True,
            "external_api_called": False,
            "record_count": len(self._collections[self.scope]),
        }

    def ensure_collection(self, *, dimension: int) -> None:
        self.dimension = dimension
        self.scope = f"{self.collection_name}:{self.namespace}:{self.dimension}"
        self._collections.setdefault(self.scope, {})

    def upsert_vectors(self, records: list[VectorRecord]) -> None:
        collection = self._collections[self.scope]
        for record in records:
            collection[record.vector_id] = record

    def query_vectors(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[VectorSearchHit]:
        filters = {key: value for key, value in (filters or {}).items() if value not in (None, "", "other")}
        hits: list[VectorSearchHit] = []
        for record in self._collections[self.scope].values():
            if not self._match_filters(record.metadata, filters):
                continue
            hits.append(
                VectorSearchHit(
                    vector_id=record.vector_id,
                    score=self._cosine(vector, record.vector),
                    metadata=record.metadata,
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:top_k]

    @staticmethod
    def _match_filters(metadata: dict, filters: dict) -> bool:
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
        right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
        return round(max(0.0, min(1.0, dot / (left_norm * right_norm))), 6)
