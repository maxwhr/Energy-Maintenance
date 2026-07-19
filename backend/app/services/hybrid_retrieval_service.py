from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.feature_reranker import FeatureFusionReranker, RerankFeatures
from app.services.query_understanding_service import QueryUnderstanding
from app.services.vector_index_service import VerifiedVectorHit


@dataclass
class HybridScoredCandidate:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float
    keyword_score: float | None = None
    vector_score: float | None = None
    vector_raw_score: float | None = None
    hybrid_score: float | None = None
    retrieval_source: str = "keyword"
    vector_backend: str | None = None
    exact_model_boost: float = 0.0
    exact_fault_code_boost: float = 0.0
    heading_boost: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float | None = None
    final_score: float | None = None
    fallback_used: bool = False
    filter_summary: dict = field(default_factory=dict)


class HybridRetrievalService:
    RRF_K = 60

    @classmethod
    def merge(
        cls,
        *,
        keyword_candidates: list[HybridScoredCandidate],
        vector_hits: list[VerifiedVectorHit],
        mode: str,
        keyword_weight: float,
        vector_weight: float,
        min_score: float,
        top_k: int,
        query_analysis: QueryUnderstanding | None = None,
        filter_summary: dict | None = None,
        fallback_used: bool = False,
        vector_similarity_threshold: float = 0.0,
        rrf_k: int | None = None,
        reranker_enabled: bool = True,
    ) -> list[HybridScoredCandidate]:
        mode = mode if mode in {"keyword", "vector", "hybrid", "hybrid_rerank"} else "keyword"
        rrf_k = max(1, int(rrf_k or cls.RRF_K))
        total_weight = max(0.0001, max(0.0, keyword_weight) + max(0.0, vector_weight))
        keyword_weight = max(0.0, keyword_weight) / total_weight
        vector_weight = max(0.0, vector_weight) / total_weight
        by_chunk: dict[UUID, HybridScoredCandidate] = {}
        max_keyword = max((item.score for item in keyword_candidates), default=0.0) or 1.0

        for rank, item in enumerate(keyword_candidates, start=1):
            normalized = max(0.0, min(1.0, item.score / max_keyword))
            by_chunk[item.chunk.id] = HybridScoredCandidate(
                chunk=item.chunk, document=item.document, score=normalized,
                keyword_score=round(normalized, 6), hybrid_score=normalized,
                rrf_score=keyword_weight / (rrf_k + rank), retrieval_source="keyword",
            )
        for rank, hit in enumerate(vector_hits, start=1):
            if hit.score < vector_similarity_threshold:
                continue
            item = by_chunk.get(hit.chunk.id)
            if item is None:
                item = HybridScoredCandidate(chunk=hit.chunk, document=hit.document, score=hit.score, retrieval_source="vector")
                by_chunk[hit.chunk.id] = item
            else:
                item.retrieval_source = "hybrid"
            item.vector_score = round(max(0.0, min(1.0, hit.score)), 6)
            item.vector_raw_score = hit.raw_score
            item.vector_backend = str(hit.metadata.get("vector_backend") or "dashvector")
            item.rrf_score += vector_weight / (rrf_k + rank)

        reranker = FeatureFusionReranker()
        document_counts: dict[UUID, int] = {}
        ranked: list[HybridScoredCandidate] = []
        for item in by_chunk.values():
            keyword = item.keyword_score or 0.0
            vector = item.vector_score or 0.0
            text = " ".join((
                item.document.title or "", item.document.product_series or "", item.document.model or "",
                " ".join(str(value) for value in ((item.document.metadata_json or {}).get("device_models") or [])),
                " ".join(str(value) for value in ((item.chunk.metadata_json or {}).get("fault_codes") or [])),
                item.chunk.section_title or "", item.chunk.content or "",
            ))
            analysis = query_analysis
            item.exact_model_boost = 0.12 if analysis and any(model.lower() in text.lower() for model in analysis.device_models) else 0.0
            item.exact_fault_code_boost = 0.15 if analysis and any(code.lower() in text.lower() for code in analysis.fault_codes) else 0.0
            exact_heading = bool(analysis and item.chunk.section_title and
                                 item.chunk.section_title.lower() in analysis.normalized_query.lower())
            item.heading_boost = 0.35 if exact_heading else (
                0.06 if analysis and any(term.lower() in (item.chunk.section_title or "").lower()
                                         for term in analysis.expanded_terms) else 0.0
            )
            rrf_normalized = min(1.0, item.rrf_score * (rrf_k + 1))
            if mode == "keyword":
                fused = keyword
                item.retrieval_source = "keyword"
            elif mode == "vector":
                exact_anchor = bool(item.exact_model_boost or item.exact_fault_code_boost or item.heading_boost >= 0.30)
                fused = max(vector, keyword * 0.95) if exact_anchor else vector
                item.retrieval_source = "vector"
            else:
                calibrated = (
                    keyword_weight * keyword + vector_weight * vector + 0.08 * rrf_normalized
                    + item.exact_model_boost + item.exact_fault_code_boost + item.heading_boost
                )
                semantic_vector_preferred = bool(
                    analysis and analysis.query_intent == "fault_diagnosis"
                    and not analysis.device_models and not analysis.fault_codes
                )
                # Exact identifiers stay lexical-first.  Unanchored symptom requests use
                # calibrated semantic fusion so a generic keyword match cannot silently
                # overwrite the independent vector ranking.
                fused = calibrated if semantic_vector_preferred else max(keyword * 0.98, calibrated)
                item.retrieval_source = "hybrid" if keyword and vector else item.retrieval_source
            document_counts[item.document.id] = document_counts.get(item.document.id, 0) + 1
            diversity_penalty = max(0, document_counts[item.document.id] - 2) * 0.04
            features = RerankFeatures(
                keyword_score=keyword, vector_score=vector,
                exact_device_model=min(1.0, item.exact_model_boost / 0.12) if item.exact_model_boost else 0,
                exact_fault_code=min(1.0, item.exact_fault_code_boost / 0.15) if item.exact_fault_code_boost else 0,
                heading_match=min(1.0, item.heading_boost / 0.06) if item.heading_boost else 0,
                kg_alias_match=1.0 if analysis and any(alias.lower() in text.lower() for alias in analysis.kg_alias_terms) else 0,
                query_intent_match=1.0 if analysis and analysis.query_intent in {"alarm_code_query", "fault_diagnosis"} else 0.5,
                diversity_penalty=diversity_penalty,
            )
            item.rerank_score = reranker.score(features) if mode == "hybrid_rerank" and reranker_enabled else None
            final = 0.70 * min(1.0, fused) + 0.30 * item.rerank_score if item.rerank_score is not None else min(1.0, fused)
            if final < min_score:
                continue
            item.hybrid_score = round(min(1.0, fused), 6)
            item.final_score = round(final, 6)
            item.score = item.final_score
            item.fallback_used = fallback_used
            item.filter_summary = {
                **(filter_summary or {}),
                "vector_similarity_threshold": vector_similarity_threshold,
                "vector_candidate_admitted": bool(vector >= vector_similarity_threshold and vector > 0),
                "reranker_applied": item.rerank_score is not None,
            }
            ranked.append(item)

        exact_model_query = bool(query_analysis and query_analysis.device_models)
        exact_fault_query = bool(query_analysis and query_analysis.fault_codes)
        ranked.sort(
            key=lambda candidate: (
                candidate.exact_fault_code_boost > 0 if exact_fault_query else True,
                candidate.exact_model_boost > 0 if exact_model_query else True,
                candidate.heading_boost >= 0.30,
                candidate.score,
                candidate.rrf_score,
                str(candidate.chunk.id),
            ),
            reverse=True,
        )
        result: list[HybridScoredCandidate] = []
        hashes: set[str] = set()
        per_document: dict[UUID, int] = {}
        for item in ranked:
            content_hash = item.chunk.content_hash or str(item.chunk.id)
            if content_hash in hashes or per_document.get(item.document.id, 0) >= 3:
                continue
            hashes.add(content_hash)
            per_document[item.document.id] = per_document.get(item.document.id, 0) + 1
            result.append(item)
            if len(result) >= top_k:
                break
        return result
