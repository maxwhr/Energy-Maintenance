from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.repositories.semantic_anchor_repository import SemanticAnchorRepository
from app.schemas.retrieval_scope import RetrievalScope
from app.services.embedding_service import EmbeddingService, EmbeddingServiceError
from app.services.semantic_query_representation_service import SemanticQueryRepresentation, SemanticQueryRepresentationService
from app.services.vector_index_service import VectorIndexService
from app.services.vector_store_adapters.base import VectorStoreAdapterError


@dataclass(frozen=True, slots=True)
class SemanticAnchorCandidate:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
    raw_score: float
    anchor_types: list[str]
    anchor_scores: dict[str, float]


@dataclass(frozen=True, slots=True)
class SemanticAnchorSearchResult:
    candidates: list[SemanticAnchorCandidate]
    query: SemanticQueryRepresentation
    diagnostics: dict


class SemanticAnchorRetrievalService:
    """Queries only the explicit semantic A/B partition and merges anchors back to source chunks."""

    def __init__(self, db: Session, *, allow_real_api: bool, collection_name: str, namespace: str):
        self.db = db
        self.settings = get_settings()
        self.allow_real_api = allow_real_api
        self.collection_name = collection_name
        self.namespace = namespace
        self.repository = SemanticAnchorRepository(db)
        self.query_service = SemanticQueryRepresentationService()

    @staticmethod
    def merge_anchor_records(records: list[tuple[object, str, float, float]]) -> dict[object, dict]:
        """Collapse multiple anchor hits to one source chunk without a Top-K monopoly."""
        merged: dict[object, dict] = {}
        for source_chunk_id, anchor_type, score, raw_score in records:
            record = merged.setdefault(source_chunk_id, {
                "score": score, "raw_score": raw_score, "types": [], "scores": {},
            })
            record["score"] = max(record["score"], score)
            record["raw_score"] = min(record["raw_score"], raw_score)
            record["types"].append(anchor_type)
            record["scores"][anchor_type] = max(record["scores"].get(anchor_type, 0.0), score)
        return merged

    def search(self, query_text: str, *, scope: RetrievalScope, top_k: int = 50) -> SemanticAnchorSearchResult:
        started = time.perf_counter()
        query = self.query_service.build(query_text)
        has_domain_terms = any((query.symptom_terms, query.action_terms, query.safety_terms, query.component_terms, query.product_context))
        if not has_domain_terms:
            return SemanticAnchorSearchResult([], query, {
                "vector_representation": "semantic_anchor", "vector_partition": self.namespace,
                "semantic_anchor_used": False, "anchor_types": [], "actual_route": "semantic_vector",
                "fallback_used": False, "fallback_reason": "unrecognised_query_in_scope", "candidate_recall_trace": [],
                "stage_latency": {"query_representation_ms": round((time.perf_counter() - started) * 1000, 3)},
            })
        service = VectorIndexService(self.db, allow_real_api=self.allow_real_api,
                                     collection_name=self.collection_name, namespace=self.namespace)
        config = service._runtime_config(provider=self.settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        embedding_started = time.perf_counter()
        try:
            embedding = EmbeddingService(allow_real_api=self.allow_real_api).embed_query(
                query.semantic_query_text, provider=config["embedding_provider"]
            )
            adapter = service._adapter(config)
            hits = adapter.query_vectors(vector=embedding.vectors[0], top_k=top_k, filters={"object_type": "semantic_anchor"})
        except (EmbeddingServiceError, VectorStoreAdapterError) as exc:
            return SemanticAnchorSearchResult([], query, {
                "vector_representation": "semantic_anchor", "vector_partition": self.namespace,
                "semantic_anchor_used": False, "anchor_types": [], "actual_route": "semantic_vector",
                "fallback_used": False, "fallback_reason": f"semantic_vector_error:{type(exc).__name__}",
                "candidate_recall_trace": [], "stage_latency": {"embedding_and_dashvector_ms": round((time.perf_counter() - embedding_started) * 1000, 3)},
            })
        anchors = self.repository.by_vector_ids(collection=config["collection_name"], namespace=self.namespace,
                                                vector_ids=[hit.vector_id for hit in hits])
        source_ids = {anchor.source_chunk_id for anchor in anchors.values()}
        rows = self.db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeChunk.id.in_(source_ids), KnowledgeDocument.id.in_(scope.allowed_document_ids),
            KnowledgeChunk.status == "active", KnowledgeDocument.status == "active", KnowledgeDocument.review_status == "approved",
        ))
        source = {chunk.id: (chunk, document) for chunk, document in rows}
        merge_records: list[tuple[object, str, float, float]] = []
        dropped = 0
        for hit in hits:
            anchor = anchors.get(hit.vector_id)
            if anchor is None or anchor.source_chunk_id not in source:
                dropped += 1
                continue
            document = source[anchor.source_chunk_id][1]
            if (document.metadata_json or {}).get("normalized_language") != scope.normalized_language:
                dropped += 1
                continue
            merge_records.append((anchor.source_chunk_id, anchor.anchor_type, hit.score, hit.raw_score))
        merged = self.merge_anchor_records(merge_records)
        candidates = []
        for source_id, record in merged.items():
            chunk, document = source[source_id]
            types = sorted(set(record["types"]))
            controlled_boost = min(0.03, max(0, len(types) - 1) * 0.01)
            candidates.append(SemanticAnchorCandidate(
                chunk=chunk, document=document, score=round(min(1.0, record["score"] + controlled_boost), 6),
                raw_score=record["raw_score"], anchor_types=types, anchor_scores={key: round(value, 6) for key, value in record["scores"].items()},
            ))
        candidates.sort(key=lambda item: (-item.score, str(item.chunk.id)))
        diagnostics = {
            "vector_representation": "semantic_anchor", "vector_partition": self.namespace,
            "semantic_anchor_used": bool(candidates), "anchor_types": sorted({item for candidate in candidates for item in candidate.anchor_types}),
            "actual_route": "semantic_vector", "fallback_used": False, "fallback_reason": None,
            "candidate_recall_trace": [{"source_chunk_id": str(candidate.chunk.id), "anchor_types": candidate.anchor_types, "score": candidate.score} for candidate in candidates[:50]],
            "raw_anchor_hits": len(hits), "merged_source_chunks": len(candidates), "post_scope_dropped": dropped,
            "collection_name": config["collection_name"], "embedding_model": config["embedding_model"], "embedding_dimension": config["embedding_dim"],
            "stage_latency": {"embedding_and_dashvector_ms": round((time.perf_counter() - embedding_started) * 1000, 3), "total_ms": round((time.perf_counter() - started) * 1000, 3)},
            "external_call_counts": {"embedding": 0 if embedding.metadata.get("cache_hit") else 1, "dashvector": 1},
        }
        return SemanticAnchorSearchResult(candidates[:top_k], query, diagnostics)
