from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.vector_index_service import VerifiedVectorHit


@dataclass
class HybridScoredCandidate:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
    keyword_score: float | None = None
    vector_score: float | None = None
    hybrid_score: float | None = None
    retrieval_source: str = "keyword"
    vector_backend: str | None = None


class HybridRetrievalService:
    @staticmethod
    def merge(
        *,
        keyword_candidates: list[HybridScoredCandidate],
        vector_hits: list[VerifiedVectorHit],
        mode: str,
        keyword_weight: float,
        vector_weight: float,
        min_score: float,
        top_k: int,
    ) -> list[HybridScoredCandidate]:
        mode = mode if mode in {"keyword", "vector", "hybrid"} else "hybrid"
        keyword_weight = max(0.0, min(1.0, keyword_weight))
        vector_weight = max(0.0, min(1.0, vector_weight))
        if keyword_weight + vector_weight <= 0:
            keyword_weight, vector_weight = 0.35, 0.65

        by_chunk: dict[UUID, HybridScoredCandidate] = {}
        max_keyword = max((item.score for item in keyword_candidates), default=0.0) or 1.0
        for item in keyword_candidates:
            normalized = round(max(0.0, item.score / max_keyword), 6)
            by_chunk[item.chunk.id] = HybridScoredCandidate(
                chunk=item.chunk,
                document=item.document,
                score=normalized,
                keyword_score=normalized,
                vector_score=None,
                hybrid_score=normalized,
                retrieval_source="keyword",
            )

        for hit in vector_hits:
            existing = by_chunk.get(hit.chunk.id)
            vector_score = round(max(0.0, min(1.0, hit.score)), 6)
            if existing:
                existing.vector_score = vector_score
                existing.retrieval_source = "hybrid"
            else:
                existing = HybridScoredCandidate(
                    chunk=hit.chunk,
                    document=hit.document,
                    score=vector_score,
                    keyword_score=None,
                    vector_score=vector_score,
                    hybrid_score=vector_score,
                    retrieval_source="vector",
                    vector_backend=str(hit.metadata.get("vector_backend") or ""),
                )
                by_chunk[hit.chunk.id] = existing
            if existing.vector_score is not None:
                existing.vector_backend = existing.vector_backend or str(hit.metadata.get("vector_backend") or "")

        merged: list[HybridScoredCandidate] = []
        for item in by_chunk.values():
            keyword_score = item.keyword_score or 0.0
            vector_score = item.vector_score or 0.0
            if mode == "keyword":
                final = keyword_score
                source = "keyword"
            elif mode == "vector":
                final = vector_score
                source = "vector"
            else:
                final = keyword_weight * keyword_score + vector_weight * vector_score
                source = "hybrid" if item.keyword_score is not None and item.vector_score is not None else item.retrieval_source
            if final < min_score:
                continue
            item.score = round(final, 6)
            item.hybrid_score = round(final, 6)
            item.retrieval_source = source
            merged.append(item)
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[:top_k]
