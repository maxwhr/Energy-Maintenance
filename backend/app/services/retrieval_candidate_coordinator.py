from __future__ import annotations

import re
import time
from concurrent.futures import Executor, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval import RetrievalQueryRequest
from app.services.hybrid_retrieval_service import HybridRetrievalService, HybridScoredCandidate
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.retrieval_pipeline_context import RetrievalPipelineContext
from app.services.retrieval_precision_policy import RetrievalPrecisionPolicy
from app.services.retrieval_text_utils import keyword_hit_count
from app.services.vector_index_service import VectorIndexService


class RetrievalCandidateCoordinator:
    """Coordinate keyword/vector recall and preserve the established ranking pipeline."""

    _shared_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="retrieval-vector")

    def __init__(
        self,
        db: Session,
        *,
        repository: RetrievalRepository,
        settings: Settings,
        query_understanding_service: QueryUnderstandingService,
        allow_real_api: bool,
        vector_collection: str | None,
        vector_namespace: str | None,
        session_factory: Callable[[], Session] | None = None,
        executor: Executor | None = None,
    ) -> None:
        self.db = db
        self.repository = repository
        self.settings = settings
        self.query_understanding_service = query_understanding_service
        self.allow_real_api = allow_real_api
        self.vector_collection = vector_collection
        self.vector_namespace = vector_namespace
        self.session_factory = session_factory or SessionLocal
        self.executor = executor or self._shared_executor

    def retrieve(self, context: RetrievalPipelineContext) -> None:
        payload = context.resolved_request
        understanding = context.query_understanding
        decision = context.strategy_decision
        candidate_limit = max(payload.top_k * 10, 80)
        context.vector_enabled = payload.enable_vector and decision.actual_strategy != "keyword"
        vector_future = None
        if context.vector_enabled:
            vector_future = self.executor.submit(
                self._vector_search_isolated,
                payload.normalized_question,
                payload.vector_top_k,
                {
                    "manufacturer": payload.manufacturer,
                    "product_series": payload.product_series,
                    "device_type": payload.device_type,
                    "document_type": payload.document_type,
                },
                context.retrieval_scope,
            )

        keyword_started = time.perf_counter()
        candidates = self.repository.list_knowledge_candidates(
            keywords=context.expansion.keywords,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            document_type=payload.document_type,
            candidate_limit=candidate_limit,
            scope=context.retrieval_scope,
        )
        context.keyword_candidates = self._score_candidates(
            candidates,
            payload,
            context.expansion.keywords,
        )
        context.latency_breakdown["keyword_retrieval"] = (
            time.perf_counter() - keyword_started
        ) * 1000

        context.vector_diagnostics = self._default_vector_diagnostics()
        if vector_future is not None:
            try:
                context.vector_candidates, context.vector_diagnostics = vector_future.result(
                    timeout=self.settings.RETRIEVAL_VECTOR_TIMEOUT_SECONDS
                )
            except FutureTimeoutError:
                context.vector_diagnostics["fallback_reason"] = "vector_time_budget_exceeded"
                context.vector_diagnostics["vector_timeout"] = True
            except Exception as exc:
                context.vector_diagnostics["fallback_reason"] = (
                    f"vector_path_error:{type(exc).__name__}"
                )

        context.vector_available = bool(
            context.vector_diagnostics.get("vector_available") and context.vector_candidates
        )
        context.vector_fallback_used = bool(
            decision.actual_strategy in {"vector", "hybrid", "hybrid_rerank"}
            and not context.vector_available
        )
        context.actual_strategy = decision.actual_strategy
        if (
            context.actual_strategy in {"vector", "hybrid", "hybrid_rerank"}
            and context.vector_fallback_used
        ):
            context.actual_strategy = "keyword"

        fusion_started = time.perf_counter()
        context.raw_merged_candidates = HybridRetrievalService.merge(
            keyword_candidates=context.keyword_candidates,
            vector_hits=context.vector_candidates,
            mode=context.actual_strategy,
            keyword_weight=(
                decision.keyword_weight
                if payload.retrieval_mode == "adaptive"
                else payload.hybrid_keyword_weight
            ),
            vector_weight=(
                decision.vector_weight
                if payload.retrieval_mode == "adaptive"
                else payload.hybrid_vector_weight
            ),
            min_score=payload.min_score,
            top_k=max(10, payload.top_k),
            query_analysis=understanding,
            filter_summary={
                "manufacturer": payload.manufacturer,
                "product_series": payload.product_series,
                "device_type": payload.device_type,
                "document_type": payload.document_type,
            },
            fallback_used=context.vector_fallback_used,
            vector_similarity_threshold=self.settings.RETRIEVAL_VECTOR_MIN_USEFUL_SCORE,
            rrf_k=self.settings.RETRIEVAL_RRF_K,
            reranker_enabled=self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
        )
        context.latency_breakdown["fusion"] = (
            time.perf_counter() - fusion_started
        ) * 1000
        self._protect_strong_keyword_evidence(context)

        refinement = ResultSetRefinementService().refine(
            context.raw_merged_candidates,
            requested_top_k=payload.top_k,
            analysis=understanding,
        )
        context.surfaced_candidates = refinement.surfaced
        context.precision_diagnostics = {
            "policy": "not_applied",
            "input": len(context.raw_merged_candidates),
            "output": len(context.surfaced_candidates),
            **refinement.diagnostics,
        }
        if payload.retrieval_mode == "adaptive":
            context.surfaced_candidates, precision_policy = RetrievalPrecisionPolicy.apply(
                context.surfaced_candidates,
                requested_top_k=payload.top_k,
                minimum_score=payload.min_score,
            )
            context.precision_diagnostics.update(
                {
                    "adaptive_precision_policy": precision_policy,
                    "output": len(context.surfaced_candidates),
                }
            )

    def _protect_strong_keyword_evidence(self, context: RetrievalPipelineContext) -> None:
        payload = context.resolved_request
        if not (
            payload.retrieval_mode == "adaptive"
            and context.actual_strategy in {"hybrid", "hybrid_rerank"}
            and context.keyword_candidates
        ):
            return
        top_raw = float(context.keyword_candidates[0].score)
        second_raw = (
            float(context.keyword_candidates[1].score)
            if len(context.keyword_candidates) > 1
            else 0.0
        )
        if top_raw < max(12.0, second_raw * 1.12):
            return
        context.raw_merged_candidates = HybridRetrievalService.merge(
            keyword_candidates=context.keyword_candidates,
            vector_hits=[],
            mode="keyword",
            keyword_weight=1.0,
            vector_weight=0.0,
            min_score=payload.min_score,
            top_k=max(10, payload.top_k),
            query_analysis=context.query_understanding,
            filter_summary={"quality_fallback": True},
            fallback_used=True,
            vector_similarity_threshold=self.settings.RETRIEVAL_VECTOR_MIN_USEFUL_SCORE,
            rrf_k=self.settings.RETRIEVAL_RRF_K,
            reranker_enabled=False,
        )
        context.actual_strategy = "keyword"
        context.quality_fallback_used = True
        context.quality_fallback_reason = "strong_keyword_evidence_protected"

    def _vector_search_isolated(self, text: str, top_k: int, filters: dict, scope=None):
        with self.session_factory() as vector_db:
            hits, diagnostics = VectorIndexService(
                vector_db,
                allow_real_api=self.allow_real_api,
                collection_name=self.vector_collection,
                namespace=self.vector_namespace,
            ).search(text, top_k=top_k, filters=filters, scope=scope)
            seen: set[UUID] = set()
            for hit in hits:
                for item in (hit.chunk, hit.document):
                    if item.id not in seen:
                        vector_db.expunge(item)
                        seen.add(item.id)
            return hits, diagnostics

    def _score_candidates(
        self,
        candidates: list[tuple[KnowledgeChunk, KnowledgeDocument]],
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> list[HybridScoredCandidate]:
        scored: list[HybridScoredCandidate] = []
        for chunk, document in candidates:
            score = self._score_candidate(chunk, document, payload, keywords)
            if score <= 0:
                continue
            scored.append(
                HybridScoredCandidate(
                    chunk=chunk,
                    document=document,
                    score=round(score, 2),
                    keyword_score=round(score, 2),
                    retrieval_source="keyword",
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    def _score_candidate(
        self,
        chunk: KnowledgeChunk,
        document: KnowledgeDocument,
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> float:
        score = 0.0
        content = chunk.content or ""
        section_title = chunk.section_title or ""
        document_title = document.title or ""
        document_summary = document.summary or ""
        document_source = document.source or ""
        joined_text = " ".join(
            [content, section_title, document_title, document_summary, document_source]
        )
        if section_title and section_title.lower() in payload.normalized_question.lower():
            score += 80.0
        if document_title and document_title.lower() in payload.normalized_question.lower():
            score += 24.0

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            score += min(keyword_hit_count(content, keyword), 4) * 2.0
            score += min(keyword_hit_count(section_title, keyword), 2) * 5.0
            score += min(keyword_hit_count(document_title, keyword), 2) * 6.0
            score += min(keyword_hit_count(document_summary, keyword), 2) * 3.0
            score += min(keyword_hit_count(document_source, keyword), 1) * 1.0

        identifiers = {
            item.lower()
            for item in re.findall(
                r"[A-Za-z0-9][A-Za-z0-9_./-]{5,}",
                payload.normalized_question,
            )
        }
        lowered_text = joined_text.lower()
        for identifier in identifiers:
            if identifier in lowered_text:
                score += 36.0
        analysis = self.query_understanding_service.understand(payload.normalized_question)
        if document.model and any(
            model.lower() == document.model.lower() for model in analysis.device_models
        ):
            score += 32.0
        metadata_codes = {
            str(item).lower() for item in (chunk.metadata_json or {}).get("fault_codes", [])
        }
        for code in analysis.fault_codes:
            if code.lower() in metadata_codes or code.lower() in lowered_text:
                score += 36.0

        if payload.alarm_code:
            alarm = payload.alarm_code.lower()
            joined_text = " ".join(
                [content, section_title, document_title, document_summary]
            ).lower()
            if alarm and alarm in joined_text:
                score += 12.0
        if payload.manufacturer and payload.manufacturer == document.manufacturer:
            score += 3.0
        if payload.product_series and payload.product_series == document.product_series:
            score += 3.0
        if payload.document_type and payload.document_type == document.document_type:
            score += 2.0
        if document.created_at:
            score += 0.2
        if chunk.char_count and chunk.char_count < 40:
            score -= 2.0
        return score

    @staticmethod
    def _default_vector_diagnostics() -> dict:
        return {
            "vector_backend": "dashvector",
            "vector_available": False,
            "fallback_reason": None,
            "raw_vector_hits": 0,
            "verified_vector_hits": 0,
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_dimension": 0,
            "warnings": [],
        }
