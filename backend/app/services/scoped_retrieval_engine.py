from __future__ import annotations

import time
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import RetrievalScope
from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.citation_validation_service import CitationValidationService
from app.services.hybrid_retrieval_service import HybridRetrievalService
from app.services.query_expansion_service import QueryExpansionService
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.retrieval_service import RetrievalService
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.vector_index_service import VectorIndexService


@dataclass(slots=True)
class ScopedRetrievalResult:
    ranked_document_ids: list[str]
    ranked_chunk_ids: list[str]
    score_breakdown: dict
    fallback_used: bool
    citation_valid: bool
    citation_coverage: float
    diagnostics: dict


class ScopedRetrievalEngine:
    """Retrieval-only engine for Pilot evaluation; it never generates answers or writes QA records."""

    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="scoped-pilot-vector")

    def __init__(self, db: Session, *, scope: RetrievalScope, allow_real_api: bool):
        self.db = db
        self.scope = scope
        self.allow_real_api = allow_real_api
        self.settings = get_settings()
        self.repository = RetrievalRepository(db)
        self.query_understanding = QueryUnderstandingService()
        self.expansion = QueryExpansionService()
        self.scorer = RetrievalService(db, allow_real_api=allow_real_api,
                                       vector_collection=scope.collection_name, vector_namespace=scope.partition_name)
        self.router = AdaptiveRetrievalStrategy()
        self.citations = CitationValidationService(db)

    def retrieve(self, request: RetrievalQueryRequest) -> ScopedRetrievalResult:
        total_started = time.perf_counter()
        stage = time.perf_counter()
        analysis = self.query_understanding.understand(request.normalized_question)
        understanding_ms = (time.perf_counter() - stage) * 1000
        route_started = time.perf_counter()
        decision = self.router.route(analysis, requested_strategy=request.retrieval_mode,
                                     reranker_enabled=self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED)
        adaptive_route_ms = (time.perf_counter() - route_started) * 1000
        expansion = self.expansion.expand(request)
        expansion.keywords = list(dict.fromkeys([*expansion.keywords, *analysis.expanded_terms]))
        if analysis.fault_codes:
            # Rare alarm identifiers are sufficient lexical keys and avoid a full set of
            # generic Chinese n-gram predicates for both known and no-answer alarms.
            expansion.keywords = list(dict.fromkeys([*analysis.fault_codes, *analysis.fault_names]))
        vector_needed = request.enable_vector and decision.actual_strategy != "keyword"
        vector_future = None
        if vector_needed:
            vector_query = self._semantic_query(request.normalized_question)
            vector_future = self._executor.submit(self._vector_search, vector_query,
                                                  request.vector_top_k, self._filters(request))
        keyword_started = time.perf_counter()
        candidates = self.repository.list_knowledge_candidates(
            keywords=expansion.keywords, manufacturer=request.manufacturer, product_series=request.product_series,
            device_type=None, document_type=request.document_type,
            candidate_limit=max(80, request.top_k * 10), scope=self.scope,
        )
        keyword_sql_ms = (time.perf_counter() - keyword_started) * 1000
        scoring_started = time.perf_counter()
        keyword_candidates = self.scorer._score_candidates(candidates, request, expansion.keywords)
        keyword_scoring_ms = (time.perf_counter() - scoring_started) * 1000
        vector_hits = []
        vector_diagnostics = {
            "vector_available": False, "external_call_counts": {"embedding": 0, "dashvector": 0},
            "fallback_reason": None, "scope_filtered_count": 0,
        }
        if vector_future is not None:
            try:
                vector_hits, vector_diagnostics = vector_future.result(timeout=self.settings.RETRIEVAL_VECTOR_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                vector_diagnostics["fallback_reason"] = "vector_time_budget_exceeded"
                vector_diagnostics["vector_timeout"] = True
            except Exception as exc:  # noqa: BLE001 - fallback is explicitly reported.
                vector_diagnostics["fallback_reason"] = f"vector_path_error:{type(exc).__name__}"
        fallback = bool(vector_needed and not (vector_diagnostics.get("vector_available") and vector_hits))
        actual_mode = "keyword" if fallback else decision.actual_strategy
        fusion_started = time.perf_counter()
        raw_merged = HybridRetrievalService.merge(
            keyword_candidates=keyword_candidates, vector_hits=vector_hits, mode=actual_mode,
            keyword_weight=decision.keyword_weight if request.retrieval_mode == "adaptive" else request.hybrid_keyword_weight,
            vector_weight=decision.vector_weight if request.retrieval_mode == "adaptive" else request.hybrid_vector_weight,
            min_score=request.min_score, top_k=max(10, request.top_k), query_analysis=analysis,
            filter_summary={"scope_id": self.scope.scope_id}, fallback_used=fallback,
            vector_similarity_threshold=self.settings.RETRIEVAL_VECTOR_MIN_USEFUL_SCORE,
            rrf_k=self.settings.RETRIEVAL_RRF_K, reranker_enabled=self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
        )
        fusion_ms = (time.perf_counter() - fusion_started) * 1000
        refinement = ResultSetRefinementService().refine(raw_merged, requested_top_k=request.top_k, analysis=analysis)
        merged = refinement.surfaced
        insufficient, abstention_reason = self.scorer._should_abstain(analysis, merged)
        recognised_evidence = any((analysis.device_models, analysis.fault_codes, analysis.fault_names,
                                   analysis.component_terms, analysis.symptom_terms, analysis.safety_terms,
                                   analysis.kg_alias_terms, analysis.document_type_filters))
        if not recognised_evidence:
            insufficient, abstention_reason = True, "unrecognised_query_in_scope"
        if insufficient:
            merged = []
        references = [{"chunk_id": item.chunk.id} for item in merged]
        citation_started = time.perf_counter()
        citation = self.citations.validate(references, candidate_chunk_ids={item.chunk.id for item in merged}, scope=self.scope)
        if insufficient and not references:
            citation.citation_valid = True
            citation.citation_coverage = 1.0
            citation.grounded_warning = None
        citation_ms = (time.perf_counter() - citation_started) * 1000
        external = vector_diagnostics.get("external_call_counts") or {"embedding": 0, "dashvector": 0}
        external = {**external, "cloud_llm": 0, "mimo": 0, "ocr": 0}
        stage_latency = {
            "query_normalization_ms": 0.0, "query_understanding_ms": round(understanding_ms, 3),
            "keyword_sql_ms": round(keyword_sql_ms, 3), "keyword_scoring_ms": round(keyword_scoring_ms, 3),
            "embedding_ms": vector_diagnostics.get("query_embedding_latency_ms", 0.0),
            "dashvector_ms": vector_diagnostics.get("dashvector_latency_ms", 0.0),
            "postgres_validation_ms": vector_diagnostics.get("postgresql_validation_latency_ms", 0.0),
            "fusion_ms": round(fusion_ms, 3), "adaptive_route_ms": round(adaptive_route_ms, 3),
            "citation_validation_ms": round(citation_ms, 3),
            "total_ms": round((time.perf_counter() - total_started) * 1000, 3),
        }
        diagnostics = {
            **vector_diagnostics, "requested_mode": request.retrieval_mode, "actual_route": actual_mode,
            "fallback_used": fallback or insufficient, "fallback_reason": abstention_reason or vector_diagnostics.get("fallback_reason"),
            "effective_scope": self.scope.public_dict(), "scope_validation_passed": all(
                item.document.id in self.scope.allowed_document_ids for item in merged),
            "collection_name": self.scope.collection_name, "partition_name": self.scope.partition_name,
            "language_filter": self.scope.normalized_language, "approval_filter": "engineering_pilot",
            "current_version_only": self.scope.current_version_only,
            "candidate_counts": {"keyword": len(keyword_candidates), "vector": len(vector_hits),
                                 "union": len({*[item.chunk.id for item in keyword_candidates], *[item.chunk.id for item in vector_hits]}),
                                 "raw": len(raw_merged), "final": len(merged)},
            "keyword_candidate_ids": [str(item.chunk.id) for item in keyword_candidates[:50]],
            "vector_candidate_ids": [str(item.chunk.id) for item in vector_hits[:50]],
            "raw_results": [{"chunk_id": str(item.chunk.id), "document_id": str(item.document.id), "score": item.score,
                             "section_title": item.chunk.section_title} for item in raw_merged[:10]],
            "surfaced_results": [{"chunk_id": str(item.chunk.id), "document_id": str(item.document.id), "score": item.score,
                                  "section_title": item.chunk.section_title} for item in merged],
            **refinement.diagnostics,
            "scope_filtered_count": int(vector_diagnostics.get("scope_filtered_count") or 0),
            "stage_latency": stage_latency, "external_call_counts": external,
            "cache_status": {"query_embedding_hit": bool(vector_diagnostics.get("query_embedding_cache_hit"))},
            "citation_valid": citation.citation_valid, "citation_coverage": citation.citation_coverage,
            "invalid_reference_ids": citation.invalid_reference_ids,
            "invalid_reference_reasons": citation.invalid_reference_reasons,
            "scope_mismatch_count": citation.scope_mismatch_count,
        }
        return ScopedRetrievalResult(
            ranked_document_ids=[str(item.document.id) for item in merged],
            ranked_chunk_ids=[str(item.chunk.id) for item in merged],
            score_breakdown={str(item.chunk.id): {"keyword_score": item.keyword_score, "vector_score": item.vector_score,
                                                 "vector_raw_score": item.vector_raw_score, "rrf_score": item.rrf_score,
                                                 "final_score": item.final_score} for item in merged},
            fallback_used=fallback or insufficient, citation_valid=citation.citation_valid,
            citation_coverage=citation.citation_coverage, diagnostics=diagnostics,
        )

    @staticmethod
    def _semantic_query(question: str) -> str:
        quoted = [item.strip() for item in re.findall(r"[“\"]([^”\"]{2,200})[”\"]", question or "")]
        if quoted:
            return max(quoted, key=len)
        normalized = re.sub(r"EDOC\d+", " ", question or "", flags=re.I)
        normalized = re.sub(r"根据华为官方|资料|章节|请说明|相关操作|注意事项", " ", normalized)
        return " ".join(normalized.split()) or question

    def _vector_search(self, text: str, top_k: int, filters: dict):
        with SessionLocal() as db:
            return VectorIndexService(db, allow_real_api=self.allow_real_api,
                                      collection_name=self.scope.collection_name,
                                      namespace=self.scope.partition_name).search(
                text, top_k=top_k, filters=filters, scope=self.scope
            )

    @staticmethod
    def _filters(request: RetrievalQueryRequest) -> dict:
        return {"manufacturer": request.manufacturer, "product_series": request.product_series,
                "device_type": None, "document_type": request.document_type}
