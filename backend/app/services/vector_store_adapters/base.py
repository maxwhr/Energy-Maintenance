from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class VectorStoreAdapterError(RuntimeError):
    pass


@dataclass(slots=True)
class VectorRecord:
    vector_id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VectorSearchHit:
    vector_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStoreAdapter:
    backend_code = "base"

    def check_status(self) -> dict:
        raise NotImplementedError

    def ensure_collection(self, *, dimension: int) -> None:
        raise NotImplementedError

    def upsert_vectors(self, records: list[VectorRecord]) -> None:
        raise NotImplementedError

    def query_vectors(
        self,
        *,
        vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[VectorSearchHit]:
        raise NotImplementedError
