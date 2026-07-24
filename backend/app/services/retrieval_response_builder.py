from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import DeviceMaintenanceRecord, User
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval import (
    RelatedHistoryItem,
    RetrievalQueryAnalysis,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
)
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.answer_generation_service import AnswerGenerationService
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.media_service import MediaService
from app.services.model_enhancement_service import ModelEnhancementService
from app.services.model_prompt_builder import ModelPromptBuilder
from app.services.retrieval_pipeline_context import RetrievalPipelineContext
from app.services.retrieval_text_utils import keyword_hit_count


MODEL_PROVIDER = "rule_based"
MODEL_NAME = "keyword_retrieval_v1"
class RetrievalResponseBuilder:
    """Build the established retrieval response without changing its API contract."""

    def __init__(
        self,
        db: Session,
        *,
        repository: RetrievalRepository,
        media_service: MediaService,
        answer_service: AnswerGenerationService,
        prompt_builder: ModelPromptBuilder,
        settings: Settings,
        vector_collection: str | None,
        vector_namespace: str | None,
    ) -> None:
        self.db = db
        self.repository = repository
        self.media_service = media_service
        self.answer_service = answer_service
        self.prompt_builder = prompt_builder
        self.settings = settings
        self.vector_collection = vector_collection
        self.vector_namespace = vector_namespace

    def build(
        self,
        context: RetrievalPipelineContext,
        current_user: User,
    ) -> RetrievalQueryResponse:
        payload = context.resolved_request
        context.related_history = self._find_related_history(
            payload,
            context.expansion.keywords,
        )
        context.knowledge_graph_context = self._resolve_kg_context(payload, current_user)
        answer = self.answer_service.generate(
            payload=payload,
            retrieved_chunks=context.retrieved_chunks,
            keywords=context.expansion.keywords,
            kg_context=context.knowledge_graph_context,
        )
        context.media_context = [
            self.media_service.media_context(item) for item in context.media_items
        ]
        context.ocr_context = (
            self.media_service.ocr_context(context.media_items)
            if payload.use_ocr_text
            else []
        )
        context.media_notice = self._media_notice(
            context.media_context,
            use_ocr_text=payload.use_ocr_text,
            ocr_context=context.ocr_context,
        )
        answer_text = answer.answer
        citation_validation = context.citation_validation
        if citation_validation is None:
            raise RuntimeError("citation validation must run before response construction")
        if citation_validation.grounded_warning:
            answer_text = f"{answer_text}\n\n{citation_validation.grounded_warning}"
        if context.media_notice:
            answer_text = f"{answer_text}\n\n{context.media_notice}"

        response = self._build_response_model(
            context,
            answer_text=answer_text,
            suggested_steps=answer.suggested_steps,
            safety_notes=answer.safety_notes,
            confidence=answer.confidence,
        )
        self._apply_model_enhancement(response, payload, current_user)
        if response.media_notice and response.media_notice not in response.answer:
            response.answer = f"{response.answer}\n\n{response.media_notice}"
        context.response = response
        return response

    def _build_response_model(
        self,
        context: RetrievalPipelineContext,
        *,
        answer_text: str,
        suggested_steps: list[str],
        safety_notes: list[str],
        confidence: float,
    ) -> RetrievalQueryResponse:
        payload = context.resolved_request
        understanding = context.query_understanding
        decision = context.strategy_decision
        scope = context.retrieval_scope
        vector_diagnostics = context.vector_diagnostics
        citation_validation = context.citation_validation
        assert citation_validation is not None
        total_ms = (time.perf_counter() - context.query_started) * 1000
        external_call_counts = (
            vector_diagnostics.get("external_call_counts")
            or self._zero_external_call_counts()
        )
        scope_validation_passed = scope is None or all(
            item.document_id in scope.allowed_document_ids
            for item in context.retrieved_chunks
        )
        raw_results = [
            {
                "chunk_id": str(item.chunk.id),
                "document_id": str(item.document.id),
                "score": item.score,
                "section_title": item.chunk.section_title,
            }
            for item in context.raw_merged_candidates[:10]
        ]
        surfaced_results = [
            {
                "chunk_id": str(item.chunk.id),
                "document_id": str(item.document.id),
                "score": item.score,
                "section_title": item.chunk.section_title,
            }
            for item in context.surfaced_candidates
        ]
        fallback_reason = (
            context.abstention_reason
            or context.quality_fallback_reason
            or vector_diagnostics.get("fallback_reason")
        )
        return RetrievalQueryResponse(
            trace_id=self._new_trace_id(),
            question=payload.normalized_question,
            answer=answer_text,
            suggested_steps=suggested_steps,
            safety_notes=safety_notes,
            references=context.references,
            retrieved_chunks=context.retrieved_chunks,
            related_history=context.related_history,
            media_items=context.media_context,
            media_notice=context.media_notice,
            ocr_context=context.ocr_context,
            kg_context=context.knowledge_graph_context,
            kg_nodes=context.knowledge_graph_context.get("kg_nodes", []),
            kg_edges=context.knowledge_graph_context.get("kg_edges", []),
            kg_evidence=context.knowledge_graph_context.get("evidence", []),
            kg_paths=context.knowledge_graph_context.get("graph_paths", []),
            confidence=confidence,
            model_provider=MODEL_PROVIDER,
            model_name=MODEL_NAME,
            retrieval_mode=context.actual_strategy,
            vector_enabled=context.vector_enabled,
            vector_available=context.vector_available,
            hybrid_used=(
                context.actual_strategy in {"hybrid", "hybrid_rerank"}
                and any(
                    item.retrieval_source == "hybrid"
                    for item in context.retrieved_chunks
                )
            ),
            vector_fallback_used=context.vector_fallback_used,
            fallback_used=(
                context.vector_fallback_used
                or context.quality_fallback_used
                or context.insufficient_evidence
            ),
            fallback_reason=fallback_reason,
            vector_backend=str(
                vector_diagnostics.get("vector_backend") or "unavailable"
            ),
            embedding_provider=vector_diagnostics.get("embedding_provider"),
            embedding_model=vector_diagnostics.get("embedding_model"),
            retrieval_diagnostics={
                **vector_diagnostics,
                "requested_retrieval_mode": payload.retrieval_mode,
                "actual_retrieval_mode": context.actual_strategy,
                "keyword_candidate_count": len(context.keyword_candidates),
                "vector_hit_count": len(context.vector_candidates),
                "precision_cutoff": context.precision_diagnostics,
                "keyword_candidate_ids": [
                    str(item.chunk.id) for item in context.keyword_candidates[:50]
                ],
                "vector_candidate_ids": [
                    str(item.chunk.id) for item in context.vector_candidates[:50]
                ],
                "raw_candidate_count": len(context.raw_merged_candidates),
                "merged_candidate_count": len(context.surfaced_candidates),
                "hybrid_keyword_weight": (
                    decision.keyword_weight
                    if payload.retrieval_mode == "adaptive"
                    else payload.hybrid_keyword_weight
                ),
                "hybrid_vector_weight": (
                    decision.vector_weight
                    if payload.retrieval_mode == "adaptive"
                    else payload.hybrid_vector_weight
                ),
                "min_score": payload.min_score,
                "citation_valid": citation_validation.citation_valid,
                "citation_coverage": citation_validation.citation_coverage,
                "invalid_reference_ids": citation_validation.invalid_reference_ids,
                "invalid_reference_reasons": citation_validation.invalid_reference_reasons,
                "scope_mismatch_count": citation_validation.scope_mismatch_count,
                "grounded_warning": citation_validation.grounded_warning,
                "query_understanding": understanding.model_dump(),
                "strategy_route": decision.model_dump(),
                "fallback_strategy": decision.fallback_strategy,
                "fallback_reason": fallback_reason,
                "quality_fallback_used": context.quality_fallback_used,
                "quality_gate_status": context.quality_gate_status,
                "raw_results": raw_results,
                "surfaced_results": surfaced_results,
                "insufficient_evidence": context.insufficient_evidence,
                "latency_breakdown_ms": {
                    "query_understanding": round(
                        context.latency_breakdown.get("query_understanding", 0.0), 3
                    ),
                    "keyword_retrieval": round(
                        context.latency_breakdown.get("keyword_retrieval", 0.0), 3
                    ),
                    "query_embedding": vector_diagnostics.get(
                        "query_embedding_latency_ms", 0.0
                    ),
                    "query_embedding_cache_hit": bool(
                        vector_diagnostics.get("query_embedding_cache_hit")
                    ),
                    "dashvector_query": vector_diagnostics.get(
                        "dashvector_latency_ms", 0.0
                    ),
                    "postgresql_validation": vector_diagnostics.get(
                        "postgresql_validation_latency_ms", 0.0
                    ),
                    "fusion": round(context.latency_breakdown.get("fusion", 0.0), 3),
                    "rerank": 0.0,
                    "citation_validation": round(
                        context.latency_breakdown.get("citation_validation", 0.0), 3
                    ),
                    "total": round(total_ms, 3),
                },
                "effective_scope": scope.public_dict() if scope else None,
                "scope_validation_passed": scope_validation_passed,
                "external_call_counts": external_call_counts,
            },
            query_analysis=RetrievalQueryAnalysis(
                normalized_query=understanding.normalized_query,
                keywords=context.expansion.keywords,
                filters={
                    "manufacturer": payload.manufacturer,
                    "product_series": payload.product_series,
                    "device_type": payload.device_type,
                    "device_id": str(payload.device_id) if payload.device_id else None,
                    "document_type": payload.document_type,
                    "fault_type": payload.fault_type,
                    "alarm_code": payload.alarm_code,
                    "top_k": payload.top_k,
                    "media_ids": [str(media_id) for media_id in payload.media_ids],
                    "use_ocr_text": payload.use_ocr_text,
                    "enable_kg_enhancement": payload.enable_kg_enhancement,
                    "retrieval_mode": payload.retrieval_mode,
                    "actual_retrieval_mode": context.actual_strategy,
                    "enable_vector": payload.enable_vector,
                    "vector_top_k": payload.vector_top_k,
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
            actual_strategy=context.actual_strategy,
            fallback_strategy=decision.fallback_strategy,
            quality_gate_status=context.quality_gate_status,
            baseline_comparison={
                "task25b_keyword_mrr": 0.82,
                "task25b_keyword_ndcg_at_10": 0.838685,
                "task25b_hybrid_rerank_mrr": 0.58,
                "task25b_hybrid_rerank_ndcg_at_10": 0.654741,
                "production_default_protected": (
                    self.settings.RETRIEVAL_DEFAULT_MODE == "keyword"
                ),
            },
            insufficient_evidence=context.insufficient_evidence,
            effective_scope=scope.public_dict() if scope else None,
            actual_route=context.actual_strategy,
            requested_mode=payload.retrieval_mode,
            collection_name=scope.collection_name if scope else self.vector_collection,
            partition_name=scope.partition_name if scope else self.vector_namespace,
            language_filter=scope.normalized_language if scope else "zh-CN",
            approval_filter=(
                "engineering_pilot"
                if scope and scope.scope_id == CHINESE_ENGINEERING_PILOT_SCOPE_ID
                else "approved"
            ),
            current_version_only=bool(scope and scope.current_version_only),
            candidate_counts={
                "keyword": len(context.keyword_candidates),
                "vector": len(context.vector_candidates),
                "final": len(context.surfaced_candidates),
            },
            scope_filtered_count=int(
                vector_diagnostics.get("scope_filtered_count") or 0
            ),
            stage_latency={
                "query_normalization_ms": 0.0,
                "query_understanding_ms": round(
                    context.latency_breakdown.get("query_understanding", 0.0), 3
                ),
                "keyword_sql_ms": round(
                    context.latency_breakdown.get("keyword_retrieval", 0.0), 3
                ),
                "keyword_scoring_ms": 0.0,
                "embedding_ms": vector_diagnostics.get(
                    "query_embedding_latency_ms", 0.0
                ),
                "dashvector_ms": vector_diagnostics.get("dashvector_latency_ms", 0.0),
                "postgres_validation_ms": vector_diagnostics.get(
                    "postgresql_validation_latency_ms", 0.0
                ),
                "fusion_ms": round(context.latency_breakdown.get("fusion", 0.0), 3),
                "adaptive_route_ms": 0.0,
                "citation_validation_ms": round(
                    context.latency_breakdown.get("citation_validation", 0.0), 3
                ),
                "total_ms": round(total_ms, 3),
            },
            raw_results=raw_results,
            surfaced_results=surfaced_results,
            raw_top_k=min(10, len(context.raw_merged_candidates)),
            surfaced_top_k=len(context.surfaced_candidates),
            cutoff_reason=str(
                context.precision_diagnostics.get("cutoff_reason") or "MAX_K"
            ),
            collapsed_groups=int(
                context.precision_diagnostics.get("collapsed_groups") or 0
            ),
            section_diversity=int(
                context.precision_diagnostics.get("section_diversity") or 0
            ),
            document_diversity=int(
                context.precision_diagnostics.get("document_diversity") or 0
            ),
            relevance_confidence=(
                float(context.surfaced_candidates[0].score)
                if context.surfaced_candidates
                else 0.0
            ),
            effective_evaluation_contract=(
                "raw_chunk_ranking_plus_surfaced_section_document_diversity"
            ),
            external_call_counts=external_call_counts,
            cache_status={
                "query_embedding_hit": bool(
                    vector_diagnostics.get("query_embedding_cache_hit")
                )
            },
            scope_validation_passed=scope_validation_passed,
        )

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
        if (
            payload.alarm_code
            and record.alarm_code
            and payload.alarm_code.lower() == record.alarm_code.lower()
        ):
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
            score += min(keyword_hit_count(text, keyword), 3)
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

    def _apply_model_enhancement(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
    ) -> None:
        if not (
            payload.enable_model_enhancement
            and payload.enable_llm
            and payload.allow_real_api
        ):
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

    def _resolve_kg_context(
        self,
        payload: RetrievalQueryRequest,
        current_user: User,
    ) -> dict:
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
    def kg_context_summary(kg_context: dict) -> dict:
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
            return (
                "OCR text from selected images was included as machine-recognized "
                "context for reference only."
            )
        if use_ocr_text:
            return (
                "OCR text was requested, but selected images do not have processed "
                "OCR text yet."
            )
        return (
            "Images are attached as human-review evidence; OCR text was not included "
            "in this answer."
        )

    @staticmethod
    def _zero_external_call_counts() -> dict[str, int]:
        return {
            "embedding": 0,
            "dashvector": 0,
            "cloud_llm": 0,
            "mimo": 0,
            "ocr": 0,
        }
