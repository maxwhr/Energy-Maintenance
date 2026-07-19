from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DeviceMaintenanceRecord, KnowledgeChunk, KnowledgeDocument, QARecord, User
from app.repositories.qa_record_repository import QARecordRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.record import QARecordRead
from app.schemas.retrieval import (
    ALLOWED_DEVICE_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_MANUFACTURERS,
    ALLOWED_PRODUCT_SERIES,
    RelatedHistoryItem,
    RetrievalQueryAnalysis,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
    RetrievalReference,
    RetrievedChunk,
)
from app.services.answer_generation_service import AnswerGenerationService
from app.services.hybrid_retrieval_service import HybridRetrievalService, HybridScoredCandidate
from app.services.media_service import MediaService, MediaServiceError
from app.services.model_enhancement_service import ModelEnhancementService
from app.services.model_prompt_builder import ModelPromptBuilder
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.query_expansion_service import QueryExpansionService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.vector_index_service import VectorIndexService
from app.core.config import get_settings
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.citation_validation_service import CitationValidationService
from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.retrieval_precision_policy import RetrievalPrecisionPolicy
from app.services.retrieval_scope_service import RetrievalScopeError, RetrievalScopeService
from app.schemas.retrieval_scope import (
    CHINESE_ENGINEERING_PILOT_SCOPE_ID,
    HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
)
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.core.database import SessionLocal


MODEL_PROVIDER = "rule_based"
MODEL_NAME = "keyword_retrieval_v1"


class RetrievalServiceError(ValueError):
    pass


class RetrievalService:
    _external_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="retrieval-vector")

    def __init__(
        self,
        db: Session,
        *,
        allow_real_api: bool | None = None,
        vector_collection: str | None = None,
        vector_namespace: str | None = None,
    ):
        self.db = db
        self.allow_real_api = get_settings().TASK25B_ALLOW_REAL_API if allow_real_api is None else allow_real_api
        self.repository = RetrievalRepository(db)
        self.qa_repository = QARecordRepository(db)
        self.expansion_service = QueryExpansionService()
        self.answer_service = AnswerGenerationService()
        self.prompt_builder = ModelPromptBuilder()
        self.media_service = MediaService(db)
        self.query_understanding_service = QueryUnderstandingService()
        self.citation_service = CitationValidationService(db)
        self.settings = get_settings()
        self.vector_collection = vector_collection
        self.vector_namespace = vector_namespace
        self.strategy_router = AdaptiveRetrievalStrategy()
        self.scope_service = RetrievalScopeService(db)

    def query(self, payload: RetrievalQueryRequest, current_user: User) -> RetrievalQueryResponse:
        self._validate_request(payload)
        unsupported_scope_reason = QuerySignalExtractionService.unsupported_scope_reason(
            payload.normalized_question,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
        )
        if unsupported_scope_reason:
            raise RetrievalServiceError(QuerySignalExtractionService.FORMAL_SUPPORT_MESSAGE)
        resolved_payload = self._resolve_device_context(payload)
        if resolved_payload.scope_id is None:
            resolved_payload = resolved_payload.model_copy(update={
                "scope_id": HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
                "manufacturer": "huawei",
                "device_type": "pv_inverter",
            })
        try:
            retrieval_scope = self.scope_service.resolve(resolved_payload.scope_id, pilot_required=False)
        except RetrievalScopeError as exc:
            raise RetrievalServiceError(str(exc)) from exc
        quality_gate_status = (
            "DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED"
            if retrieval_scope and retrieval_scope.scope_id == CHINESE_ENGINEERING_PILOT_SCOPE_ID
            else self.settings.RETRIEVAL_QUALITY_GATE_STATUS
        )
        try:
            media_items = self.media_service.resolve_media_items(
                resolved_payload.media_ids,
                device_id=resolved_payload.device_id,
            )
        except MediaServiceError as exc:
            raise RetrievalServiceError(str(exc)) from exc
        search_payload = self._payload_with_media_context(resolved_payload, media_items)
        query_started = time.perf_counter()
        stage_started = query_started
        understanding = self.query_understanding_service.understand(search_payload.normalized_question)
        query_understanding_ms = (time.perf_counter() - stage_started) * 1000
        decision = self.strategy_router.route(
            understanding,
            requested_strategy=resolved_payload.retrieval_mode,
            reranker_enabled=self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
        )
        expansion = self.expansion_service.expand(search_payload)
        expansion.keywords = list(dict.fromkeys([*expansion.keywords, *understanding.expanded_terms]))
        candidate_limit = max(resolved_payload.top_k * 10, 80)
        vector_enabled = resolved_payload.enable_vector and decision.actual_strategy != "keyword"
        vector_future = None
        if vector_enabled:
            vector_future = self._external_executor.submit(
                self._vector_search_isolated,
                resolved_payload.normalized_question,
                resolved_payload.vector_top_k,
                {
                    "manufacturer": resolved_payload.manufacturer,
                    "product_series": resolved_payload.product_series,
                    "device_type": resolved_payload.device_type,
                    "document_type": resolved_payload.document_type,
                },
                retrieval_scope,
            )
        keyword_started = time.perf_counter()
        candidates = self.repository.list_knowledge_candidates(
            keywords=expansion.keywords,
            manufacturer=resolved_payload.manufacturer,
            product_series=resolved_payload.product_series,
            device_type=resolved_payload.device_type,
            document_type=resolved_payload.document_type,
            candidate_limit=candidate_limit,
            scope=retrieval_scope,
        )
        scored_candidates = self._score_candidates(candidates, resolved_payload, expansion.keywords)
        keyword_latency_ms = (time.perf_counter() - keyword_started) * 1000
        vector_hits = []
        vector_diagnostics = {
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
        if vector_future is not None:
            try:
                vector_hits, vector_diagnostics = vector_future.result(
                    timeout=self.settings.RETRIEVAL_VECTOR_TIMEOUT_SECONDS
                )
            except FutureTimeoutError:
                vector_diagnostics["fallback_reason"] = "vector_time_budget_exceeded"
                vector_diagnostics["vector_timeout"] = True
            except Exception as exc:
                vector_diagnostics["fallback_reason"] = f"vector_path_error:{type(exc).__name__}"
        vector_available = bool(vector_diagnostics.get("vector_available") and vector_hits)
        vector_fallback_used = bool(decision.actual_strategy in {"vector", "hybrid", "hybrid_rerank"} and not vector_available)
        actual_mode = decision.actual_strategy
        if actual_mode in {"vector", "hybrid", "hybrid_rerank"} and vector_fallback_used:
            actual_mode = "keyword"
        fusion_started = time.perf_counter()
        raw_merged_candidates = HybridRetrievalService.merge(
            keyword_candidates=scored_candidates,
            vector_hits=vector_hits,
            mode=actual_mode,
            keyword_weight=decision.keyword_weight if resolved_payload.retrieval_mode == "adaptive" else resolved_payload.hybrid_keyword_weight,
            vector_weight=decision.vector_weight if resolved_payload.retrieval_mode == "adaptive" else resolved_payload.hybrid_vector_weight,
            min_score=resolved_payload.min_score,
            top_k=max(10, resolved_payload.top_k),
            query_analysis=understanding,
            filter_summary={
                "manufacturer": resolved_payload.manufacturer,
                "product_series": resolved_payload.product_series,
                "device_type": resolved_payload.device_type,
                "document_type": resolved_payload.document_type,
            },
            fallback_used=vector_fallback_used,
            vector_similarity_threshold=self.settings.RETRIEVAL_VECTOR_MIN_USEFUL_SCORE,
            rrf_k=self.settings.RETRIEVAL_RRF_K,
            reranker_enabled=self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
        )
        fusion_latency_ms = (time.perf_counter() - fusion_started) * 1000
        quality_fallback_used = False
        quality_fallback_reason = None
        if resolved_payload.retrieval_mode == "adaptive" and actual_mode in {"hybrid", "hybrid_rerank"} and scored_candidates:
            top_raw = float(scored_candidates[0].score)
            second_raw = float(scored_candidates[1].score) if len(scored_candidates) > 1 else 0.0
            if top_raw >= max(12.0, second_raw * 1.12):
                raw_merged_candidates = HybridRetrievalService.merge(
                    keyword_candidates=scored_candidates, vector_hits=[], mode="keyword",
                    keyword_weight=1.0, vector_weight=0.0, min_score=resolved_payload.min_score,
                    top_k=max(10, resolved_payload.top_k), query_analysis=understanding,
                    filter_summary={"quality_fallback": True}, fallback_used=True,
                    vector_similarity_threshold=self.settings.RETRIEVAL_VECTOR_MIN_USEFUL_SCORE,
                    rrf_k=self.settings.RETRIEVAL_RRF_K, reranker_enabled=False,
                )
                actual_mode = "keyword"
                quality_fallback_used = True
                quality_fallback_reason = "strong_keyword_evidence_protected"
        refinement = ResultSetRefinementService().refine(raw_merged_candidates, requested_top_k=resolved_payload.top_k, analysis=understanding)
        merged_candidates = refinement.surfaced
        precision_diagnostics = {"policy": "not_applied", "input": len(raw_merged_candidates), "output": len(merged_candidates), **refinement.diagnostics}
        if resolved_payload.retrieval_mode == "adaptive":
            merged_candidates, precision_policy = RetrievalPrecisionPolicy.apply(
                merged_candidates,
                requested_top_k=resolved_payload.top_k,
                minimum_score=resolved_payload.min_score,
            )
            precision_diagnostics.update({"adaptive_precision_policy": precision_policy, "output": len(merged_candidates)})
        insufficient_evidence, abstention_reason = self._should_abstain(understanding, merged_candidates)
        recognised_evidence = any((understanding.device_models, understanding.fault_codes, understanding.fault_names,
                                   understanding.component_terms, understanding.symptom_terms, understanding.safety_terms,
                                   understanding.kg_alias_terms, understanding.document_type_filters))
        if resolved_payload.scope_id in {
            CHINESE_ENGINEERING_PILOT_SCOPE_ID, HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
        } and not recognised_evidence:
            insufficient_evidence, abstention_reason = True, "unrecognised_query_in_scope"
        if insufficient_evidence:
            merged_candidates = []
        retrieved_chunks = [self._candidate_to_retrieved_chunk(candidate) for candidate in merged_candidates]
        references = self._build_references(retrieved_chunks)
        citation_started = time.perf_counter()
        citation_validation = self.citation_service.validate(
            references,
            candidate_chunk_ids={item.chunk_id for item in retrieved_chunks},
            scope=retrieval_scope,
        )
        citation_latency_ms = (time.perf_counter() - citation_started) * 1000
        related_history = self._find_related_history(resolved_payload, expansion.keywords)
        kg_context = self._resolve_kg_context(resolved_payload, current_user)
        answer = self.answer_service.generate(
            payload=resolved_payload,
            retrieved_chunks=retrieved_chunks,
            keywords=expansion.keywords,
            kg_context=kg_context,
        )
        trace_id = self._new_trace_id()
        media_context = [self.media_service.media_context(item) for item in media_items]
        ocr_context = self.media_service.ocr_context(media_items) if resolved_payload.use_ocr_text else []
        media_notice = self._media_notice(
            media_context,
            use_ocr_text=resolved_payload.use_ocr_text,
            ocr_context=ocr_context,
        )
        answer_text = answer.answer
        if citation_validation.grounded_warning:
            answer_text = f"{answer_text}\n\n{citation_validation.grounded_warning}"
        if media_notice:
            answer_text = f"{answer_text}\n\n{media_notice}"
        response = RetrievalQueryResponse(
            trace_id=trace_id,
            question=resolved_payload.normalized_question,
            answer=answer_text,
            suggested_steps=answer.suggested_steps,
            safety_notes=answer.safety_notes,
            references=references,
            retrieved_chunks=retrieved_chunks,
            related_history=related_history,
            media_items=media_context,
            media_notice=media_notice,
            ocr_context=ocr_context,
            kg_context=kg_context,
            kg_nodes=kg_context.get("kg_nodes", []),
            kg_edges=kg_context.get("kg_edges", []),
            kg_evidence=kg_context.get("evidence", []),
            kg_paths=kg_context.get("graph_paths", []),
            confidence=answer.confidence,
            model_provider=MODEL_PROVIDER,
            model_name=MODEL_NAME,
            retrieval_mode=actual_mode,
            vector_enabled=vector_enabled,
            vector_available=vector_available,
            hybrid_used=actual_mode in {"hybrid", "hybrid_rerank"} and any(item.retrieval_source == "hybrid" for item in retrieved_chunks),
            vector_fallback_used=vector_fallback_used,
            fallback_used=vector_fallback_used or quality_fallback_used or insufficient_evidence,
            fallback_reason=abstention_reason or quality_fallback_reason or vector_diagnostics.get("fallback_reason"),
            vector_backend=str(vector_diagnostics.get("vector_backend") or "unavailable"),
            embedding_provider=vector_diagnostics.get("embedding_provider"),
            embedding_model=vector_diagnostics.get("embedding_model"),
            retrieval_diagnostics={
                **vector_diagnostics,
                "requested_retrieval_mode": resolved_payload.retrieval_mode,
                "actual_retrieval_mode": actual_mode,
                "keyword_candidate_count": len(scored_candidates),
                "vector_hit_count": len(vector_hits),
                "precision_cutoff": precision_diagnostics,
                "keyword_candidate_ids": [str(item.chunk.id) for item in scored_candidates[:50]],
                "vector_candidate_ids": [str(item.chunk.id) for item in vector_hits[:50]],
                "raw_candidate_count": len(raw_merged_candidates), "merged_candidate_count": len(merged_candidates),
                "hybrid_keyword_weight": decision.keyword_weight if resolved_payload.retrieval_mode == "adaptive" else resolved_payload.hybrid_keyword_weight,
                "hybrid_vector_weight": decision.vector_weight if resolved_payload.retrieval_mode == "adaptive" else resolved_payload.hybrid_vector_weight,
                "min_score": resolved_payload.min_score,
                "citation_valid": citation_validation.citation_valid,
                "citation_coverage": citation_validation.citation_coverage,
                "invalid_reference_ids": citation_validation.invalid_reference_ids,
                "invalid_reference_reasons": citation_validation.invalid_reference_reasons,
                "scope_mismatch_count": citation_validation.scope_mismatch_count,
                "grounded_warning": citation_validation.grounded_warning,
                "query_understanding": understanding.model_dump(),
                "strategy_route": decision.model_dump(),
                "fallback_strategy": decision.fallback_strategy,
                "fallback_reason": abstention_reason or quality_fallback_reason or vector_diagnostics.get("fallback_reason"),
                "quality_fallback_used": quality_fallback_used,
                "quality_gate_status": quality_gate_status,
                "raw_results": [{"chunk_id": str(item.chunk.id), "document_id": str(item.document.id), "score": item.score,
                                 "section_title": item.chunk.section_title} for item in raw_merged_candidates[:10]],
                "surfaced_results": [{"chunk_id": str(item.chunk.id), "document_id": str(item.document.id), "score": item.score,
                                      "section_title": item.chunk.section_title} for item in merged_candidates],
                "insufficient_evidence": insufficient_evidence,
                "latency_breakdown_ms": {
                    "query_understanding": round(query_understanding_ms, 3),
                    "keyword_retrieval": round(keyword_latency_ms, 3),
                    "query_embedding": vector_diagnostics.get("query_embedding_latency_ms", 0.0),
                    "query_embedding_cache_hit": bool(vector_diagnostics.get("query_embedding_cache_hit")),
                    "dashvector_query": vector_diagnostics.get("dashvector_latency_ms", 0.0),
                    "postgresql_validation": vector_diagnostics.get("postgresql_validation_latency_ms", 0.0),
                    "fusion": round(fusion_latency_ms, 3),
                    "rerank": 0.0,
                    "citation_validation": round(citation_latency_ms, 3),
                    "total": round((time.perf_counter() - query_started) * 1000, 3),
                },
                "effective_scope": retrieval_scope.public_dict() if retrieval_scope else None,
                "scope_validation_passed": retrieval_scope is None or all(
                    item.document_id in retrieval_scope.allowed_document_ids for item in retrieved_chunks
                ),
                "external_call_counts": vector_diagnostics.get("external_call_counts") or {
                    "embedding": 0, "dashvector": 0, "cloud_llm": 0, "mimo": 0, "ocr": 0
                },
            },
            query_analysis=RetrievalQueryAnalysis(
                normalized_query=understanding.normalized_query,
                keywords=expansion.keywords,
                filters={
                    "manufacturer": resolved_payload.manufacturer,
                    "product_series": resolved_payload.product_series,
                    "device_type": resolved_payload.device_type,
                    "device_id": str(resolved_payload.device_id) if resolved_payload.device_id else None,
                    "document_type": resolved_payload.document_type,
                    "fault_type": resolved_payload.fault_type,
                    "alarm_code": resolved_payload.alarm_code,
                    "top_k": resolved_payload.top_k,
                    "media_ids": [str(media_id) for media_id in resolved_payload.media_ids],
                    "use_ocr_text": resolved_payload.use_ocr_text,
                    "enable_kg_enhancement": resolved_payload.enable_kg_enhancement,
                    "retrieval_mode": resolved_payload.retrieval_mode,
                    "actual_retrieval_mode": actual_mode,
                    "enable_vector": resolved_payload.enable_vector,
                    "vector_top_k": resolved_payload.vector_top_k,
                },
                query_intent=understanding.query_intent,
                device_models=understanding.device_models,
                fault_codes=understanding.fault_codes,
                fault_names=understanding.fault_names,
                component_terms=understanding.component_terms,
                symptom_terms=understanding.symptom_terms,
                safety_terms=understanding.safety_terms,
                time_terms=understanding.time_terms,
                document_type_filters=understanding.document_type_filters,
                expanded_terms=understanding.expanded_terms,
                kg_alias_terms=understanding.kg_alias_terms,
                negative_terms=understanding.negative_terms,
                confidence=understanding.confidence,
            ),
            recommended_strategy=decision.recommended_strategy,
            actual_strategy=actual_mode,
            fallback_strategy=decision.fallback_strategy,
            quality_gate_status=quality_gate_status,
            baseline_comparison={
                "task25b_keyword_mrr": 0.82,
                "task25b_keyword_ndcg_at_10": 0.838685,
                "task25b_hybrid_rerank_mrr": 0.58,
                "task25b_hybrid_rerank_ndcg_at_10": 0.654741,
                "production_default_protected": self.settings.RETRIEVAL_DEFAULT_MODE == "keyword",
            },
            insufficient_evidence=insufficient_evidence,
            effective_scope=retrieval_scope.public_dict() if retrieval_scope else None,
            actual_route=actual_mode,
            requested_mode=resolved_payload.retrieval_mode,
            collection_name=retrieval_scope.collection_name if retrieval_scope else self.vector_collection,
            partition_name=retrieval_scope.partition_name if retrieval_scope else self.vector_namespace,
            language_filter=retrieval_scope.normalized_language if retrieval_scope else "zh-CN",
            approval_filter=(
                "engineering_pilot"
                if retrieval_scope and retrieval_scope.scope_id == CHINESE_ENGINEERING_PILOT_SCOPE_ID
                else "approved"
            ),
            current_version_only=bool(retrieval_scope and retrieval_scope.current_version_only),
            candidate_counts={"keyword": len(scored_candidates), "vector": len(vector_hits), "final": len(merged_candidates)},
            scope_filtered_count=int(vector_diagnostics.get("scope_filtered_count") or 0),
            stage_latency={
                "query_normalization_ms": 0.0, "query_understanding_ms": round(query_understanding_ms, 3),
                "keyword_sql_ms": round(keyword_latency_ms, 3), "keyword_scoring_ms": 0.0,
                "embedding_ms": vector_diagnostics.get("query_embedding_latency_ms", 0.0),
                "dashvector_ms": vector_diagnostics.get("dashvector_latency_ms", 0.0),
                "postgres_validation_ms": vector_diagnostics.get("postgresql_validation_latency_ms", 0.0),
                "fusion_ms": round(fusion_latency_ms, 3), "adaptive_route_ms": 0.0,
                "citation_validation_ms": round(citation_latency_ms, 3),
                "total_ms": round((time.perf_counter() - query_started) * 1000, 3),
            },
            raw_results=[{"chunk_id": str(item.chunk.id), "document_id": str(item.document.id), "score": item.score,
                          "section_title": item.chunk.section_title} for item in raw_merged_candidates[:10]],
            surfaced_results=[{"chunk_id": str(item.chunk.id), "document_id": str(item.document.id), "score": item.score,
                              "section_title": item.chunk.section_title} for item in merged_candidates],
            raw_top_k=min(10, len(raw_merged_candidates)), surfaced_top_k=len(merged_candidates),
            cutoff_reason=str(refinement.diagnostics.get("cutoff_reason") or "MAX_K"),
            collapsed_groups=int(refinement.diagnostics.get("collapsed_groups") or 0),
            section_diversity=int(refinement.diagnostics.get("section_diversity") or 0),
            document_diversity=int(refinement.diagnostics.get("document_diversity") or 0),
            relevance_confidence=float(merged_candidates[0].score) if merged_candidates else 0.0,
            effective_evaluation_contract="raw_chunk_ranking_plus_surfaced_section_document_diversity",
            external_call_counts=vector_diagnostics.get("external_call_counts") or {
                "embedding": 0, "dashvector": 0, "cloud_llm": 0, "mimo": 0, "ocr": 0
            },
            cache_status={"query_embedding_hit": bool(vector_diagnostics.get("query_embedding_cache_hit"))},
            scope_validation_passed=retrieval_scope is None or all(
                item.document_id in retrieval_scope.allowed_document_ids for item in retrieved_chunks
            ),
        )
        self._apply_model_enhancement(response, resolved_payload, current_user)
        if response.media_notice and response.media_notice not in response.answer:
            response.answer = f"{response.answer}\n\n{response.media_notice}"
        self._save_qa_record(response, resolved_payload, current_user, media_items)
        return response

    def _vector_search_isolated(self, text: str, top_k: int, filters: dict, scope=None):
        with SessionLocal() as vector_db:
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

    def _should_abstain(self, analysis, candidates: list[HybridScoredCandidate]) -> tuple[bool, str | None]:
        if not candidates:
            return True, "no_verified_candidates"
        if any(term in analysis.normalized_query for term in ("不存在", "未收录", "未知型号", "未知告警", "没有相关")):
            return True, "explicit_no_answer_intent"
        evidence_text = " ".join(
            " ".join((
                item.document.title or "", item.document.product_series or "", item.document.model or "",
                " ".join(str(value) for value in ((item.document.metadata_json or {}).get("device_models") or [])),
                " ".join(str(value) for value in ((item.chunk.metadata_json or {}).get("fault_codes") or [])),
                item.chunk.section_title or "", item.chunk.content or "",
            ))
            for item in candidates[:5]
        ).lower()
        if analysis.device_models and not any(model.lower() in evidence_text for model in analysis.device_models):
            return True, "exact_device_model_not_supported"
        if analysis.fault_codes and not any(code.lower() in evidence_text for code in analysis.fault_codes):
            return True, "exact_fault_code_not_supported"
        top_score = float(candidates[0].score)
        second_score = float(candidates[1].score) if len(candidates) > 1 else 0.0
        if top_score < self.settings.RETRIEVAL_ABSTENTION_MIN_SCORE:
            return True, "top_score_below_abstention_threshold"
        if top_score < 0.55 and len(candidates) > 1 and top_score - second_score < self.settings.RETRIEVAL_ABSTENTION_MIN_MARGIN:
            return True, "insufficient_score_margin"
        return False, None

    def list_records(
        self,
        *,
        device_id: UUID | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        records, total = self.qa_repository.list_qa_records(
            device_id=device_id,
            manufacturer=manufacturer,
            product_series=product_series,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [QARecordRead.model_validate(record).model_dump(mode="json") for record in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_record_detail(self, trace_id: str) -> dict | None:
        record = self.qa_repository.get_by_trace_id(trace_id)
        if not record:
            return None
        return QARecordRead.model_validate(record).model_dump(mode="json")

    @staticmethod
    def _validate_request(payload: RetrievalQueryRequest) -> None:
        if not payload.normalized_question:
            raise RetrievalServiceError("query or question must not be empty")
        if payload.top_k < 1 or payload.top_k > 10:
            raise RetrievalServiceError("top_k must be between 1 and 10")
        if payload.vector_top_k < 1 or payload.vector_top_k > 50:
            raise RetrievalServiceError("vector_top_k must be between 1 and 50")
        if payload.retrieval_mode not in {"keyword", "vector", "hybrid", "hybrid_rerank", "adaptive"}:
            raise RetrievalServiceError("unsupported retrieval_mode")
        if payload.hybrid_keyword_weight < 0 or payload.hybrid_vector_weight < 0:
            raise RetrievalServiceError("hybrid weights must be non-negative")
        if payload.hybrid_keyword_weight + payload.hybrid_vector_weight <= 0:
            raise RetrievalServiceError("hybrid weights must not both be zero")
        if payload.min_score < 0 or payload.min_score > 1:
            raise RetrievalServiceError("min_score must be between 0 and 1")
        if payload.manufacturer and payload.manufacturer not in ALLOWED_MANUFACTURERS:
            raise RetrievalServiceError("manufacturer must be huawei or sungrow")
        if payload.product_series and payload.product_series not in ALLOWED_PRODUCT_SERIES:
            raise RetrievalServiceError("unsupported product_series")
        if payload.device_type not in ALLOWED_DEVICE_TYPES:
            raise RetrievalServiceError("device_type must be pv_inverter")
        if payload.document_type and payload.document_type not in ALLOWED_DOCUMENT_TYPES:
            raise RetrievalServiceError("unsupported document_type")
        if len(payload.media_ids) > 10:
            raise RetrievalServiceError("media_ids supports at most 10 media items")

    def _resolve_device_context(self, payload: RetrievalQueryRequest) -> RetrievalQueryRequest:
        if not payload.device_id:
            return payload
        device = self.repository.get_device(payload.device_id)
        if not device:
            raise RetrievalServiceError("Device not found")
        update_data = payload.model_dump()
        update_data["manufacturer"] = payload.manufacturer or device.manufacturer
        update_data["product_series"] = payload.product_series or device.product_series
        update_data["device_type"] = payload.device_type or device.device_type
        return RetrievalQueryRequest(**update_data)

    def _payload_with_media_context(
        self,
        payload: RetrievalQueryRequest,
        media_items: list,
    ) -> RetrievalQueryRequest:
        media_texts = self.media_service.media_context_texts(
            media_items,
            include_ocr_text=payload.use_ocr_text,
        )
        if not media_texts:
            return payload
        data = payload.model_dump()
        data["query"] = None
        data["question"] = "\n".join([payload.normalized_question, *media_texts])
        return RetrievalQueryRequest(**data)

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
        joined_text = " ".join([content, section_title, document_title, document_summary, document_source])
        if section_title and section_title.lower() in payload.normalized_question.lower():
            score += 80.0
        if document_title and document_title.lower() in payload.normalized_question.lower():
            score += 24.0

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            score += min(self._hit_count(content, keyword), 4) * 2.0
            score += min(self._hit_count(section_title, keyword), 2) * 5.0
            score += min(self._hit_count(document_title, keyword), 2) * 6.0
            score += min(self._hit_count(document_summary, keyword), 2) * 3.0
            score += min(self._hit_count(document_source, keyword), 1) * 1.0

        # Rare identifiers are strong lexical evidence across manuals, alarm codes and
        # controlled engineering corpora. This is query-derived and never uses labels.
        identifiers = {
            item.lower()
            for item in re.findall(r"[A-Za-z0-9][A-Za-z0-9_./-]{5,}", payload.normalized_question)
        }
        lowered_text = joined_text.lower()
        for identifier in identifiers:
            if identifier in lowered_text:
                score += 36.0
        analysis = self.query_understanding_service.understand(payload.normalized_question)
        if document.model and any(model.lower() == document.model.lower() for model in analysis.device_models):
            score += 32.0
        metadata_codes = {str(item).lower() for item in (chunk.metadata_json or {}).get("fault_codes", [])}
        for code in analysis.fault_codes:
            if code.lower() in metadata_codes or code.lower() in lowered_text:
                score += 36.0

        if payload.alarm_code:
            alarm = payload.alarm_code.lower()
            joined_text = " ".join([content, section_title, document_title, document_summary]).lower()
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
    def _hit_count(text: str, keyword: str) -> int:
        if not text or not keyword:
            return 0
        return len(re.findall(re.escape(keyword.lower()), text.lower()))

    @staticmethod
    def _candidate_to_retrieved_chunk(candidate: HybridScoredCandidate) -> RetrievedChunk:
        chunk = candidate.chunk
        document = candidate.document
        return RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            document_title=document.title,
            chunk_index=chunk.chunk_index,
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            content=chunk.content,
            score=candidate.score,
            manufacturer=document.manufacturer,
            product_series=document.product_series,
            device_type=document.device_type,
            document_type=document.document_type,
            source=document.source,
            created_at=chunk.created_at,
            keyword_score=candidate.keyword_score,
            vector_score=candidate.vector_score,
            vector_raw_score=candidate.vector_raw_score,
            hybrid_score=candidate.hybrid_score,
            exact_model_boost=candidate.exact_model_boost,
            exact_fault_code_boost=candidate.exact_fault_code_boost,
            heading_boost=candidate.heading_boost,
            rrf_score=candidate.rrf_score,
            rerank_score=candidate.rerank_score,
            final_score=candidate.final_score,
            fallback_used=candidate.fallback_used,
            filter_summary=candidate.filter_summary,
            retrieval_source=candidate.retrieval_source,
            vector_backend=candidate.vector_backend,
        )

    def _build_references(self, chunks: list[RetrievedChunk]) -> list[RetrievalReference]:
        references: list[RetrievalReference] = []
        for chunk in chunks:
            references.append(
                RetrievalReference(
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    quote=self._quote(chunk.content),
                    manufacturer=chunk.manufacturer,
                    product_series=chunk.product_series,
                    device_type=chunk.device_type,
                    document_type=chunk.document_type,
                    source=chunk.source,
                    score=chunk.score,
                )
            )
        return references

    @staticmethod
    def _quote(content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        return compact[:180]

    def _find_related_history(
        self,
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> list[RelatedHistoryItem]:
        if not payload.include_history or not payload.device_id:
            return []
        records = self.repository.list_history_candidates(
            device_id=payload.device_id,
            keywords=keywords,
            fault_type=payload.fault_type,
            alarm_code=payload.alarm_code,
            candidate_limit=20,
        )
        if not records:
            records = self.repository.list_recent_history_by_device(
                device_id=payload.device_id,
                candidate_limit=20,
            )
        scored = sorted(
            records,
            key=lambda record: self._score_history(record, payload, keywords),
            reverse=True,
        )
        return [self._history_payload(record) for record in scored[:3]]

    def _score_history(
        self,
        record: DeviceMaintenanceRecord,
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> float:
        score = 1.0
        if payload.fault_type and payload.fault_type == record.fault_type:
            score += 8.0
        if payload.alarm_code and record.alarm_code and payload.alarm_code.lower() == record.alarm_code.lower():
            score += 8.0
        text = " ".join(
            [
                record.fault_description or "",
                record.root_cause or "",
                record.repair_action or "",
                record.verification_result or "",
            ]
        )
        for keyword in keywords[:40]:
            score += min(self._hit_count(text, keyword), 3)
        return score

    @staticmethod
    def _history_payload(record: DeviceMaintenanceRecord) -> RelatedHistoryItem:
        return RelatedHistoryItem(
            record_id=record.id,
            device_id=record.device_id,
            fault_type=record.fault_type,
            alarm_code=record.alarm_code,
            fault_description=record.fault_description,
            root_cause=record.root_cause,
            repair_action=record.repair_action,
            verification_result=record.verification_result,
            is_recurrent=record.is_recurrent,
            completed_at=record.completed_at,
        )

    def _save_qa_record(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
        media_items: list,
    ) -> None:
        stored_history = [item.model_dump(mode="json") for item in response.related_history]
        stored_history.extend(
            {
                "record_type": "media_context",
                **item.model_dump(mode="json"),
            }
            for item in response.media_items
        )
        stored_history.extend(
            {
                "record_type": "ocr_context",
                **item,
            }
            for item in response.ocr_context
        )
        if response.kg_context:
            stored_history.append(
                {
                    "record_type": "kg_context_summary",
                    **self._kg_context_summary(response.kg_context),
                }
            )
        stored_history.append(
            {
                "record_type": "retrieval_diagnostics",
                "retrieval_mode": response.retrieval_mode,
                "vector_backend": response.vector_backend,
                "vector_available": response.vector_available,
                "hybrid_used": response.hybrid_used,
                "vector_fallback_used": response.vector_fallback_used,
                "embedding_provider": response.embedding_provider,
                "embedding_model": response.embedding_model,
                "diagnostics": response.retrieval_diagnostics,
            }
        )
        record = QARecord(
            trace_id=response.trace_id,
            device_id=payload.device_id,
            question=response.question,
            normalized_query=response.question,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            document_type=payload.document_type,
            answer=response.answer,
            references=[item.model_dump(mode="json") for item in response.references],
            retrieved_chunks=[item.model_dump(mode="json") for item in response.retrieved_chunks],
            suggested_steps=response.suggested_steps,
            safety_notes=response.safety_notes,
            related_history=stored_history,
            model_provider=response.model_provider,
            model_name=response.model_name,
            confidence=response.confidence,
            created_by=current_user.id,
        )
        try:
            self.qa_repository.create_qa_record(record)
            self.media_service.link_to_qa(media_items, response.trace_id)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise RetrievalServiceError(f"QA record write failed: {exc}") from exc

    def _apply_model_enhancement(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
    ) -> None:
        if not payload.enable_model_enhancement:
            return
        prompt = self.prompt_builder.build_retrieval_prompt(
            question=response.question,
            answer=response.answer,
            suggested_steps=response.suggested_steps,
            safety_notes=response.safety_notes,
            references=response.references,
            media_context=response.media_items,
            kg_context=response.kg_context,
        )
        enhancement = ModelEnhancementService(self.db).enhance(
            prompt=prompt,
            task_type="qa",
            requested_provider=payload.model_provider,
            allow_fallback=payload.allow_model_fallback,
            current_user=current_user,
            default_provider=MODEL_PROVIDER,
            default_model_name=MODEL_NAME,
        )
        if enhancement.content:
            response.answer = enhancement.content
        ModelEnhancementService.apply_metadata(response, enhancement)

    def _resolve_kg_context(self, payload: RetrievalQueryRequest, current_user: User) -> dict:
        if not payload.enable_kg_enhancement:
            return {}
        return KnowledgeGraphService(self.db).business_context(
            current_user=current_user,
            device_id=payload.device_id,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            fault_type=payload.fault_type,
            alarm_code=payload.alarm_code,
            question=payload.normalized_question,
        )

    @staticmethod
    def _kg_context_summary(kg_context: dict) -> dict:
        summary = kg_context.get("summary") or {}
        return {
            "summary": summary,
            "matched_nodes": [
                {
                    "id": item.get("id"),
                    "node_type": item.get("node_type"),
                    "display_name": item.get("display_name"),
                }
                for item in (kg_context.get("matched_nodes") or [])[:8]
            ],
            "related_causes": kg_context.get("related_causes", [])[:5],
            "inspection_items": kg_context.get("inspection_items", [])[:5],
            "recommended_actions": kg_context.get("recommended_actions", [])[:5],
            "safety_risks": kg_context.get("safety_risks", [])[:5],
            "evidence_count": len(kg_context.get("evidence") or []),
        }

    @staticmethod
    def _new_trace_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"qa_{timestamp}_{uuid4().hex[:10]}"

    @staticmethod
    def _media_notice(
        media_items: list,
        *,
        use_ocr_text: bool = False,
        ocr_context: list[dict] | None = None,
    ) -> str | None:
        if not media_items:
            return None
        if use_ocr_text and ocr_context:
            return "OCR text from selected images was included as machine-recognized context for reference only."
        if use_ocr_text:
            return "OCR text was requested, but selected images do not have processed OCR text yet."
        return "Images are attached as human-review evidence; OCR text was not included in this answer."

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise RetrievalServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise RetrievalServiceError("page_size must be between 1 and 100")
