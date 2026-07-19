from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Device, KnowledgeChunk, KnowledgeDocument, QARecord, User
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.retrieval_repository import RetrievalRepository
from app.repositories.qa_record_repository import QARecordRepository
from app.schemas.query_aware_retrieval import QueryAwareCandidateRead, QueryAwareSearchRequest, QueryAwareSearchResponse
from app.schemas.retrieval import RetrievedChunk, RetrievalQueryRequest
from app.schemas.query_understanding import ClarificationRequest, QueryUnderstandingResult
from app.schemas.retrieval_plan import RetrievalPlan
from app.schemas.retrieval_scope import HUAWEI_SUN2000_COMPETITION_SCOPE_ID
from app.services.citation_validation_service import CitationValidationResult
from app.services.answer_generation_service import AnswerGenerationService
from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.conversation_retrieval_context_service import ConversationRetrievalContextService
from app.services.deterministic_evidence_rerank_service import (
    DeterministicEvidenceRerankResult,
    DeterministicEvidenceRerankService,
)
from app.services.dedicated_rerank_service import DedicatedRerankService
from app.services.embedding_service import EmbeddingService
from app.services.grounded_answer_boundary_service import GroundedAnswerBoundaryService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService
from app.services.multi_query_retrieval_service import MultiQueryRetrievalService
from app.services.post_rerank_constraint_service import PostRerankConstraintResult, PostRerankConstraintService
from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_confidence_service import RetrievalConfidenceService
from app.services.retrieval_plan_service import RetrievalPlanService
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.rrf_fusion_service import QueryAwareCandidate, RRFFusionService
from app.services.candidate_feature_context import CandidateFeatureContext
from app.services.citation_batch_builder_service import CitationBatchBuilderService
from app.services.query_variant_deduplication_service import QueryVariantDeduplicationService
from app.services.rag_performance_trace_service import RagPerformanceTraceService
from app.services.retrieval_scope_context import RetrievalScopeContext


class QueryAwareRetrievalError(ValueError):
    pass


@dataclass(slots=True)
class UnderstandingBundle:
    understanding: QueryUnderstandingResult
    signals: object
    assessment: object
    clarification: object
    stage_latency: dict[str, float]


class QueryAwareRetrievalService:
    FORMAL_SCOPE_ID = HUAWEI_SUN2000_COMPETITION_SCOPE_ID
    PARTITION = HUAWEI_SUN2000_COMPETITION_SCOPE_ID

    def __init__(self, db: Session, *, current_user: User):
        self.db = db
        self.current_user = current_user
        if current_user is None:
            raise QueryAwareRetrievalError("authenticated user is required")
        # Authentication may have opened a transaction on the request session.
        # Detach the already-loaded actor and release that read connection before
        # external provider work starts. Conversation writes can safely acquire a
        # new connection later through the same Session.
        if current_user in db:
            db.expunge(current_user)
            db.rollback()
        self.signals = QuerySignalExtractionService()
        self.completeness = QuestionCompletenessService()
        self.clarification = ClarificationPolicyService()
        self.context = ConversationRetrievalContextService(db)
        self.qa_repository = QARecordRepository(db)
        self.answer_service = AnswerGenerationService()
        with SessionLocal() as scope_db:
            self.scope = RetrievalScopeService(scope_db).resolve(
                self.FORMAL_SCOPE_ID, pilot_required=True,
            )
        self.scope_context = RetrievalScopeContext.from_scope(self.scope)

    def understand(
        self,
        query: str,
        *,
        enable_llm: bool = True,
        allow_real_api: bool = False,
        conversation_state: dict | None = None,
    ) -> UnderstandingBundle:
        timings: dict[str, float] = {}
        started = time.perf_counter()
        signals = self.signals.extract(query)
        timings["signal_extraction_ms"] = self._elapsed(started)
        started = time.perf_counter()
        assessment = self.completeness.assess(signals)
        timings["question_completeness_ms"] = self._elapsed(started)
        started = time.perf_counter()
        orchestration = QueryUnderstandingOrchestratorService().understand(
            signals=signals,
            assessment=assessment,
            enable_llm=enable_llm,
            allow_real_api=allow_real_api,
            conversation_state=conversation_state,
        )
        understanding = orchestration.understanding
        timings["query_understanding_ms"] = self._elapsed(started)
        decision = self.clarification.decide(signals=signals, assessment=assessment, understanding=understanding)
        understanding.needs_clarification = decision.status == "CLARIFICATION_REQUIRED"
        understanding.clarifying_question = decision.questions[0] if decision.questions else None
        return UnderstandingBundle(understanding, signals, assessment, decision, timings)

    def plan(
        self,
        query: str,
        *,
        enable_llm: bool = True,
        allow_real_api: bool = False,
    ) -> tuple[UnderstandingBundle, RetrievalPlan]:
        bundle = self.understand(query, enable_llm=enable_llm, allow_real_api=allow_real_api)
        plan = RetrievalPlanService().build(
            bundle.understanding,
            clarification=bundle.clarification,
            required_scope=self.scope.scope_id,
        )
        return bundle, plan

    def search(self, payload: QueryAwareSearchRequest) -> QueryAwareSearchResponse:
        if not payload.request_id:
            payload = payload.model_copy(update={"request_id": f"req_{uuid4().hex}"})
        settings = get_settings()
        if not settings.RAG_PERFORMANCE_TRACE_ENABLED:
            return self._search_impl(payload)
        with RagPerformanceTraceService.trace(
            trace_id=str(uuid4()),
            query=payload.query,
            scope_fingerprint=self.scope_context.fingerprint,
            mode=payload.retrieval_mode,
            cache_status="OFF" if not settings.RAG_QUERY_RESULT_CACHE_ENABLED else "ENABLED",
        ):
            response = self._search_impl(payload)
            RagPerformanceTraceService.update_stages(response.stage_latency)
            return response

    def _search_impl(self, payload: QueryAwareSearchRequest) -> QueryAwareSearchResponse:
        total_started = time.perf_counter()
        original_query = payload.query
        effective_query = payload.query
        conversation_id = payload.conversation_id
        context_state: dict = {}
        if conversation_id:
            session = self.context.get(conversation_id, current_user=self.current_user)
            original_query = session.original_query
            context_state = dict(session.state_json or {})
            effective_query = str(context_state.get("merged_query") or payload.query)
        unsupported_scope_reason = self.signals.unsupported_scope_reason(effective_query)
        if unsupported_scope_reason:
            return self._unsupported_scope_response(
                payload,
                query=payload.query,
                reason=unsupported_scope_reason,
                total_started=total_started,
            )
        unsafe_request_reason = self.signals.unsafe_request_reason(effective_query)
        if unsafe_request_reason:
            return self._unsafe_request_response(
                payload,
                query=payload.query,
                reason=unsafe_request_reason,
                total_started=total_started,
            )
        pre_signals = self.signals.extract(effective_query)
        pre_assessment = self.completeness.assess(pre_signals)
        normalized_effective_query = pre_signals.normalized_query
        prefetch_executor: ThreadPoolExecutor | None = None
        prefetch_future = None
        likely_vector_path = (
            payload.allow_real_api
            and get_settings().TASK25B_ALLOW_REAL_API
            # Deterministic understanding completes in sub-millisecond time, so
            # a one-text prefetch only duplicates the later multi-variant batch.
            # Prefetch is useful solely when the optional ambiguity provider can
            # overlap real network latency.
            and get_settings().RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED
            and pre_assessment.status not in {"AMBIGUOUS", "INSUFFICIENT_INFORMATION"}
            and not (pre_signals.device_models or pre_signals.alarm_codes or pre_signals.alarm_names)
        )
        if likely_vector_path:
            prefetch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="r5-query-embedding")
            prefetch_future = prefetch_executor.submit(self._prefetch_query_embedding, normalized_effective_query)
        try:
            bundle = self.understand(
                effective_query,
                enable_llm=payload.enable_llm,
                allow_real_api=payload.allow_real_api,
                conversation_state=context_state,
            )
        except Exception:
            if prefetch_executor is not None:
                prefetch_executor.shutdown(wait=True)
            raise
        bundle.understanding.original_query = original_query
        if conversation_id and not (context_state.get("unresolved_missing_information") or []):
            bundle.assessment = bundle.assessment.model_copy(update={
                "status": "CLEAR",
                "missing_information": [],
                "ambiguity": False,
                "ambiguity_options": [],
                "reason_codes": ["conversation_clarification_resolved"],
            })
            bundle.understanding.completeness_status = "CLEAR"
            bundle.understanding.missing_information = []
            bundle.understanding.ambiguity = False
            bundle.understanding.ambiguity_options = []
            bundle.clarification = self.clarification.decide(
                signals=bundle.signals,
                assessment=bundle.assessment,
                understanding=bundle.understanding,
            )
            bundle.understanding.needs_clarification = False
            bundle.understanding.clarifying_question = None
        if payload.retrieval_mode == "fast":
            bundle.understanding.fast_path = True
            bundle.understanding.query_understanding_used = False
            bundle.understanding.query_understanding_mode = "FAST_PATH"
            bundle.understanding.needs_clarification = False
            bundle.understanding.missing_information = []
            bundle.understanding.ambiguity = False
            bundle.understanding.clarifying_question = None
            bundle.understanding.normalized_semantics["missing_slots"] = []
            bundle.assessment = bundle.assessment.model_copy(update={
                "status": "CLEAR",
                "missing_information": [],
                "ambiguity": False,
                "ambiguity_options": [],
                "reason_codes": ["explicit_fast_path"],
            })
            bundle.clarification = self.clarification.decide(
                signals=bundle.signals,
                assessment=bundle.assessment,
                understanding=bundle.understanding,
            )
        elif payload.retrieval_mode == "deep":
            bundle.understanding.fast_path = False
        if not conversation_id and payload.persist_result and bundle.clarification.status != "NO_CLARIFICATION":
            session = self.context.create(
                original_query=original_query,
                signals=bundle.signals,
                clarification=bundle.clarification,
                current_user=self.current_user,
            )
            conversation_id = session.conversation_id
        if bundle.clarification.status == "CLARIFICATION_REQUIRED":
            stage = self._complete_timings(bundle.stage_latency, total_started)
            return QueryAwareSearchResponse(
                request_id=payload.request_id,
                conversation_id=conversation_id,
                original_query=original_query,
                normalized_query=bundle.understanding.normalized_query,
                canonical_question=bundle.understanding.canonical_question,
                primary_intent=bundle.understanding.primary_intent,
                requested_information=list(bundle.understanding.requested_information),
                confirmed_facts=bundle.understanding.confirmed_facts,
                missing_information=bundle.clarification.missing_information,
                ambiguity=bundle.understanding.ambiguity,
                needs_clarification=True,
                clarifying_question=bundle.clarification.questions[0] if bundle.clarification.questions else None,
                query_understanding_used=bundle.understanding.query_understanding_used,
                query_understanding_fallback=bundle.understanding.fallback_used,
                query_understanding_mode=bundle.understanding.query_understanding_mode,
                confidence_status="NEEDS_CLARIFICATION",
                retrieval_confidence=0.0,
                query_signals=bundle.signals.model_dump(mode="json"),
                trace_id=self._trace_id(payload.request_id),
                abstained=True,
                message="请补充必要的设备型号、告警代码或具体现象后再检索。",
                persistence_status="not_persisted_clarification",
                stage_latency=stage,
                answer_boundary={
                    "confirmed_evidence": [], "possible_explanations": [], "recommended_checks": [],
                    "safety_warnings": [], "clarifying_question": bundle.clarification.questions[0] if bundle.clarification.questions else None,
                    "insufficient_evidence_notice": None, "hypotheses_promoted_to_fact": False,
                    "unsupported_repair_instructions": 0,
                },
                quality_status="R5_CLARIFICATION_REQUIRED",
                model_routing=self._model_routing(bundle.understanding, {}),
                minimax_diagnostics=self._minimax_diagnostics(bundle.understanding),
                diagnostics={"repair_instructions_suppressed": True, "scope_expanded": False},
            )
        started = time.perf_counter()
        plan = RetrievalPlanService().build(
            bundle.understanding,
            clarification=bundle.clarification,
            candidate_top_k=max(50, payload.top_k * 5),
            required_scope=self.scope.scope_id,
        )
        variant_deduplication = QueryVariantDeduplicationService().deduplicate(plan)
        plan = variant_deduplication.plan
        bundle.stage_latency["retrieval_plan_ms"] = self._elapsed(started)
        precomputed_vectors: dict[str, list[float]] = {}
        precomputed_embedding_ms = 0.0
        if prefetch_future is not None:
            try:
                vector, precomputed_embedding_ms = prefetch_future.result()
                precomputed_vectors[normalized_effective_query] = vector
            except Exception:  # noqa: BLE001 - normal retrieval records the provider failure.
                precomputed_vectors = {}
                precomputed_embedding_ms = 0.0
            finally:
                assert prefetch_executor is not None
                prefetch_executor.shutdown(wait=True)
        retrieval = MultiQueryRetrievalService(allow_real_api=payload.allow_real_api).retrieve(
            plan=plan,
            understanding=bundle.understanding,
            scope=self.scope,
            precomputed_query_vectors=precomputed_vectors,
            precomputed_embedding_ms=precomputed_embedding_ms,
            precomputed_embedding_calls=1 if precomputed_vectors else 0,
        )
        channel_latency = retrieval.diagnostics.get("channel_latency_ms") or {}
        bundle.stage_latency.update({
            "keyword_ms": round(max(channel_latency.get("EXACT_KEYWORD", 0.0), channel_latency.get("SCOPED_KEYWORD", 0.0)), 3),
            "embedding_ms": round(float(retrieval.diagnostics.get("embedding_ms") or 0.0), 3),
            "raw_vector_ms": round(channel_latency.get("RAW_VECTOR", 0.0), 3),
            "semantic_unit_ms": round(channel_latency.get("SEMANTIC_UNIT", 0.0), 3),
        })
        started = time.perf_counter()
        fusion_service = RRFFusionService()
        fused = fusion_service.fuse(
            retrieval.rankings,
            top_k=plan.fusion_candidate_limit,
            channel_weights=plan.channel_weights,
            query_weights=plan.query_weights,
        )
        bundle.stage_latency["fusion_ms"] = self._elapsed(started)
        raw_read = [self._read(item) for item in fused]
        pre_citation = CitationBatchBuilderService().validate_candidates(fused, scope=self.scope)
        citation_status = {item.chunk_id: item.chunk_id in set(pre_citation.valid_reference_ids) for item in fused}
        started = time.perf_counter()
        pre_guard = PreRerankHardGuardService().apply(fused, understanding=bundle.understanding)
        bundle.stage_latency["pre_rerank_guard_ms"] = self._elapsed(started)
        started = time.perf_counter()
        if not get_settings().RAG_DETERMINISTIC_RERANK_ENABLED:
            deterministic = DeterministicEvidenceRerankResult(
                candidates=pre_guard.candidates,
                diagnostics={
                    "executed": False,
                    "weights_version": get_settings().DETERMINISTIC_RERANK_WEIGHTS_VERSION,
                    "candidates_in": len(pre_guard.candidates),
                    "candidates_out": len(pre_guard.candidates),
                    "order_changed": False,
                    "score_breakdown": {},
                    "skipped_reason": "DISABLED",
                },
            )
        else:
            deterministic = DeterministicEvidenceRerankService().rerank(
                pre_guard.candidates,
                understanding=bundle.understanding,
                citation_status=citation_status,
            )
        feature_context_diagnostics = CandidateFeatureContext().capture(deterministic.candidates)
        bundle.stage_latency["deterministic_rerank_ms"] = self._elapsed(started)
        started = time.perf_counter()
        dedicated = DedicatedRerankService().rerank(
            pre_guard.candidates,
            understanding=bundle.understanding,
            allow_real_api=payload.allow_real_api,
            fallback_candidates=deterministic.candidates,
        )
        bundle.stage_latency["dedicated_rerank_ms"] = self._elapsed(started)
        bundle.stage_latency["tiebreak_ms"] = 0.0
        started = time.perf_counter()
        if dedicated.diagnostics.get("success"):
            post_constraints = PostRerankConstraintService().apply(
                dedicated.candidates,
                understanding=bundle.understanding,
            )
        else:
            post_constraints = PostRerankConstraintResult(
                dedicated.candidates,
                {
                    "executed": False,
                    "status": "SKIPPED_TO_PRESERVE_DETERMINISTIC_FALLBACK_ORDER",
                    "fallback": True,
                    "candidate_additions": 0,
                    "candidate_removals": 0,
                    "source_modifications": 0,
                    "citation_modifications": 0,
                },
            )
        bundle.stage_latency["post_rerank_constraint_ms"] = self._elapsed(started)
        bundle.stage_latency["rerank_ms"] = round(
            bundle.stage_latency["pre_rerank_guard_ms"]
            + bundle.stage_latency["deterministic_rerank_ms"]
            + bundle.stage_latency["dedicated_rerank_ms"]
            + bundle.stage_latency["post_rerank_constraint_ms"],
            3,
        )
        started = time.perf_counter()
        refinement = ResultSetRefinementService().refine_query_aware(
            post_constraints.candidates, requested_top_k=payload.top_k,
        )
        surfaced = self._retain_signal_supported_candidates(refinement.surfaced, bundle.signals)
        bundle.stage_latency["refinement_ms"] = self._elapsed(started)
        started = time.perf_counter()
        citation = CitationBatchBuilderService().validate_candidates(surfaced, scope=self.scope)
        bundle.stage_latency["citation_ms"] = self._elapsed(started)
        started = time.perf_counter()
        confidence = RetrievalConfidenceService().assess(
            understanding=bundle.understanding,
            clarification=bundle.clarification,
            candidates=surfaced,
            citation=citation,
        )
        bundle.stage_latency["confidence_ms"] = self._elapsed(started)
        boundary = GroundedAnswerBoundaryService().build(
            understanding=bundle.understanding,
            clarification=bundle.clarification,
            confidence=confidence,
            candidates=surfaced,
        )
        all_citations = [{
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "document_title": item.document_title,
            "chunk_index": item.chunk.chunk_index,
            "manufacturer": item.document.manufacturer,
            "product_series": item.document.product_series,
            "device_type": item.document.device_type,
            "document_type": item.document.document_type,
            "section_title": item.section_title,
            "page_number": item.page_number,
            "source": item.document.source,
            "score": round(float(item.final_score), 6),
            "source_locator": item.source_locator,
            "quote": self._quote(item.content),
            "source_type": citation.source_type_by_reference.get(item.chunk_id),
        } for item in surfaced]
        valid_id_set = set(citation.valid_reference_ids)
        citations = [item for item in all_citations if item["chunk_id"] in valid_id_set]
        invalid_citations = [
            {**item, "reason": citation.invalid_reference_reasons.get(item["chunk_id"], "invalid_reference")}
            for item in all_citations if item["chunk_id"] not in valid_id_set
        ]
        started = time.perf_counter()
        retrieved_chunks = self._answer_chunks(surfaced, valid_id_set)
        generated_answer = self.answer_service.generate(
            payload=self._answer_payload(bundle),
            retrieved_chunks=retrieved_chunks,
            keywords=self._answer_keywords(bundle),
            kg_context=None,
        )
        bundle.stage_latency["answer_generation_ms"] = self._elapsed(started)
        abstained = not bool(retrieved_chunks)
        stage = self._complete_timings(bundle.stage_latency, total_started)
        response = QueryAwareSearchResponse(
            request_id=payload.request_id,
            conversation_id=conversation_id,
            original_query=original_query,
            normalized_query=bundle.understanding.normalized_query,
            canonical_question=bundle.understanding.canonical_question,
            primary_intent=bundle.understanding.primary_intent,
            requested_information=list(bundle.understanding.requested_information),
            confirmed_facts=bundle.understanding.confirmed_facts,
            missing_information=bundle.clarification.missing_information,
            ambiguity=bundle.understanding.ambiguity,
            needs_clarification=False,
            clarifying_question=bundle.clarification.questions[0] if bundle.clarification.questions else None,
            query_understanding_used=bundle.understanding.query_understanding_used,
            query_understanding_fallback=bundle.understanding.fallback_used,
            query_understanding_mode=bundle.understanding.query_understanding_mode,
            retrieval_plan=plan,
            requested_channels=list(plan.requested_channels),
            actual_channels=retrieval.actual_channels,
            executed_channels=retrieval.executed_channels,
            nonempty_channels=retrieval.nonempty_channels,
            failed_channels=retrieval.failed_channels,
            fallback_channels=retrieval.fallback_channels,
            generated_queries=[item.query for item in plan.query_variants],
            rerank_used=bool(
                dedicated.diagnostics.get("success") or deterministic.diagnostics.get("executed")
            ),
            rerank_fallback=bool(dedicated.diagnostics.get("fallback")),
            confidence_status=confidence.status,
            retrieval_confidence=confidence.confidence,
            answer=generated_answer.answer,
            suggested_steps=generated_answer.suggested_steps,
            safety_notes=generated_answer.safety_notes,
            confidence=generated_answer.confidence,
            references=citations,
            retrieved_chunks=[item.model_dump(mode="json") for item in retrieved_chunks],
            trace_id=self._trace_id(payload.request_id),
            query_signals=bundle.signals.model_dump(mode="json"),
            retrieval_diagnostics={
                "requested_mode": payload.retrieval_mode,
                "actual_channels": retrieval.actual_channels,
                "failed_channels": retrieval.failed_channels,
                "fallback_channels": retrieval.fallback_channels,
                "candidate_count": len(fused),
                "surfaced_count": len(surfaced),
                "signal_supported_count": len(surfaced),
                "valid_reference_count": len(citations),
                "scope_id": self.scope.scope_id,
                "scope_document_count": len(self.scope.allowed_document_ids),
            },
            abstained=abstained,
            message=(
                "已基于华为 SUN2000 正式知识范围生成可追溯回答。"
                if not abstained
                else "当前华为 SUN2000 正式知识范围内没有足够可靠的资料，系统已安全拒答。"
            ),
            provider_status={
                "generation": "rule_based",
                "keyword": "available",
                "hybrid": "available" if any(channel in {"RAW_VECTOR", "SEMANTIC_UNIT"} for channel in retrieval.nonempty_channels) else "blocked_or_not_used",
                "fallback_used": bool(retrieval.fallback_channels),
            },
            raw_results=raw_read,
            surfaced_results=[self._read(item) for item in surfaced],
            citations=citations,
            valid_citations=citations,
            invalid_citations=invalid_citations,
            citation_validity_ratio=citation.citation_validity_ratio,
            citation_coverage_ratio=citation.citation_coverage_ratio,
            confidence_reason_codes=confidence.reason_codes,
            entity_conflicts=confidence.entity_conflicts,
            evidence_conflicts=confidence.evidence_conflicts,
            structured_model_diagnostics={
                "query_understanding": bundle.understanding.structured_model_diagnostics,
                "pre_rerank_hard_guard": pre_guard.diagnostics,
                "deterministic_rerank": deterministic.diagnostics,
                "dedicated_rerank": dedicated.diagnostics,
                "post_rerank_constraints": post_constraints.diagnostics,
                "minimax_tiebreak": {"called": False, "skipped_reason": "NOT_IN_RANKING_PATH"},
            },
            model_routing=self._model_routing(bundle.understanding, dedicated.diagnostics),
            minimax_diagnostics=self._minimax_diagnostics(bundle.understanding, {}),
            deterministic_rerank=self._public_rerank_diagnostics(deterministic.diagnostics),
            minimax_tiebreak={"called": False, "skipped_reason": "NOT_IN_RANKING_PATH"},
            dedicated_rerank=self._public_dedicated_rerank_diagnostics(dedicated.diagnostics),
            post_rerank_constraints=post_constraints.diagnostics,
            raw_vector_trace=(retrieval.diagnostics.get("raw_vector_trace") or {}),
            rrf_vote_breakdown=fusion_service.last_diagnostics,
            collapse_groups=refinement.diagnostics.get("collapsed_groups") or [],
            candidate_channel_counts=retrieval.channel_counts,
            stage_latency=stage,
            scope=self.scope.scope_id,
            partition=self.scope.partition_name,
            answer_boundary=boundary,
            quality_status="HUAWEI_SUN2000_ABSTAINED" if abstained else "HUAWEI_SUN2000_KEYWORD_READY",
            diagnostics={
                "scope_validation_passed": all(item.scope_validation_passed for item in surfaced),
                "scope_expanded": False,
                "citation_valid": citation.citation_valid,
                "citation_coverage": citation.citation_coverage,
                "candidate_additions_by_rerank": int(dedicated.diagnostics.get("candidate_additions") or 0) + int(post_constraints.diagnostics.get("candidate_additions") or 0),
                "candidate_source_modifications_by_rerank": int(dedicated.diagnostics.get("source_modifications") or 0) + int(post_constraints.diagnostics.get("source_modifications") or 0),
                "candidate_citation_modifications_by_rerank": int(dedicated.diagnostics.get("citation_modifications") or 0) + int(post_constraints.diagnostics.get("citation_modifications") or 0),
                "pre_rerank_hard_guard": pre_guard.diagnostics,
                "dedicated_rerank_provider_status": dedicated.diagnostics.get("provider_status"),
                "candidate_recall_evaluation_limit": plan.candidate_top_k,
                "fusion_candidate_limit": plan.fusion_candidate_limit,
                "evidence_identity_version": "task25b_r3_dev_r5_r5_evidence_identity_v1",
                "relevant_candidates_lost_without_reason": refinement.diagnostics.get("relevant_candidates_lost_without_reason", 0),
                "original_query_retained": original_query == bundle.understanding.original_query,
                "query_hash": hashlib.sha256(effective_query.encode("utf-8")).hexdigest(),
                "partition": self.scope.partition_name,
                "retrieval": retrieval.diagnostics,
                "query_variant_deduplication": variant_deduplication.diagnostics,
                "candidate_feature_context": feature_context_diagnostics,
                "scope_fingerprint": self.scope_context.fingerprint,
                "confidence_reasons": confidence.reason_codes,
                "entity_conflicts": confidence.entity_conflicts,
                "evidence_conflicts": confidence.evidence_conflicts,
                "rrf": fusion_service.last_diagnostics,
                "refinement": refinement.diagnostics,
                "kg_alias_status": plan.kg_alias_status,
            },
        )
        started = time.perf_counter()
        self._persist_qa_record(response, payload, bundle.signals)
        response.stage_latency["qa_persistence_ms"] = self._elapsed(started)
        response.stage_latency["total_ms"] = self._elapsed(total_started)
        return response

    def clarify(self, payload: ClarificationRequest) -> QueryAwareSearchResponse:
        signals = self.signals.extract(payload.clarification)
        item = self.context.merge(
            conversation_id=payload.conversation_id,
            clarification_text=payload.clarification,
            clarification_signals=signals,
            current_user=self.current_user,
        )
        merged_query = str((item.state_json or {}).get("merged_query") or payload.clarification)
        return self.search(QueryAwareSearchRequest(
            query=merged_query,
            conversation_id=payload.conversation_id,
            enable_llm=payload.enable_llm,
            allow_real_api=False,
        ))

    def _persist_qa_record(
        self,
        response: QueryAwareSearchResponse,
        payload: QueryAwareSearchRequest,
        signals,
    ) -> None:
        if not payload.persist_result:
            response.persistence_status = "skipped_preview"
            return
        if not response.trace_id:
            raise QueryAwareRetrievalError("query-aware response is missing trace_id")
        diagnostics_record = {
            "record_type": "query_aware_retrieval_diagnostics",
            "request_id": response.request_id,
            "query_signals": response.query_signals,
            "retrieval_mode": payload.retrieval_mode,
            "provider_status": response.provider_status,
            "abstained": response.abstained,
            "scope_id": self.scope.scope_id,
            "retrieval_diagnostics": response.retrieval_diagnostics,
            "candidate_chunk_ids": [item.chunk_id for item in response.raw_results],
            "final_chunk_ids": [str(item.get("chunk_id")) for item in response.retrieved_chunks if item.get("chunk_id")],
            "reference_chunk_ids": [str(item.get("chunk_id")) for item in response.references if item.get("chunk_id")],
        }
        unsupported = bool(response.retrieval_diagnostics.get("unsupported_scope_reason"))
        record = QARecord(
            trace_id=response.trace_id,
            question=response.original_query,
            normalized_query=response.normalized_query,
            manufacturer=None if unsupported else (signals.manufacturer or "huawei"),
            product_series=None if unsupported else (signals.product_family or "SUN2000"),
            device_id=self._persisted_device_id(payload),
            device_type="pv_inverter",
            answer=response.answer,
            references=response.references,
            retrieved_chunks=response.retrieved_chunks,
            suggested_steps=response.suggested_steps,
            safety_notes=response.safety_notes,
            related_history=[diagnostics_record],
            model_provider="rule_based",
            model_name="huawei_sun2000_query_aware_keyword_v1",
            confidence=response.confidence,
            created_by=self.current_user.id,
        )
        try:
            existing = self.qa_repository.get_by_trace_id(response.trace_id)
            if existing is not None:
                if existing.question != response.original_query:
                    raise QueryAwareRetrievalError("request_id has already been used for a different query")
                response.persistence_status = "reused_idempotent_record"
                response.qa_record_id = str(existing.id)
                return
            self.qa_repository.create_qa_record(record)
            self.db.commit()
            response.persistence_status = "persisted"
            response.qa_record_id = str(record.id)
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.qa_repository.get_by_trace_id(response.trace_id)
            if existing is None:
                self._mark_persistence_failed(response, "idempotency_conflict_unresolved")
                return
            if existing.question != response.original_query:
                raise QueryAwareRetrievalError("request_id has already been used for a different query") from exc
            response.persistence_status = "reused_idempotent_record"
            response.qa_record_id = str(existing.id)
        except SQLAlchemyError:
            self.db.rollback()
            self._mark_persistence_failed(response, "database_write_failed")

    @staticmethod
    def _mark_persistence_failed(response: QueryAwareSearchResponse, reason: str) -> None:
        response.persistence_status = "failed"
        response.qa_record_id = None
        response.retrieval_diagnostics["persistence_failure_reason"] = reason
        warning = "问答结果已生成，但记录保存失败，请稍后重试。"
        response.message = f"{response.message} {warning}".strip()

    def _persisted_device_id(self, payload: QueryAwareSearchRequest) -> UUID | None:
        raw_device_id = (payload.device_context or {}).get("device_id")
        if not raw_device_id:
            return None
        try:
            device_id = UUID(str(raw_device_id))
        except (TypeError, ValueError):
            return None
        return device_id if self.db.get(Device, device_id) is not None else None

    def _unsupported_scope_response(
        self,
        payload: QueryAwareSearchRequest,
        *,
        query: str,
        reason: str,
        total_started: float,
        confidence_status: str = "UNSUPPORTED_SCOPE",
        answer_message: str | None = None,
        safety_notes: list[str] | None = None,
        diagnostic_key: str = "unsupported_scope_reason",
        quality_status: str = "HUAWEI_SUN2000_UNSUPPORTED_SCOPE",
    ) -> QueryAwareSearchResponse:
        signals = self.signals.extract(query)
        support_message = answer_message or self.signals.FORMAL_SUPPORT_MESSAGE
        response_safety_notes = safety_notes or [
            "请勿将其他厂家或非 SUN2000 产品的检修步骤直接套用于华为 SUN2000 设备。"
        ]
        response = QueryAwareSearchResponse(
            request_id=payload.request_id,
            conversation_id=payload.conversation_id,
            original_query=query,
            normalized_query=signals.normalized_query,
            canonical_question=signals.normalized_query,
            primary_intent="GENERAL",
            requested_information=list(signals.requested_information),
            confirmed_facts={},
            confidence_status=confidence_status,
            retrieval_confidence=0.0,
            answer=support_message,
            suggested_steps=[],
            safety_notes=response_safety_notes,
            confidence=0.0,
            references=[],
            retrieved_chunks=[],
            trace_id=self._trace_id(payload.request_id),
            query_signals=signals.model_dump(mode="json"),
            retrieval_diagnostics={
                "scope_id": self.scope.scope_id,
                "scope_document_count": len(self.scope.allowed_document_ids),
                diagnostic_key: reason,
                "candidate_count": 0,
                "surfaced_count": 0,
                "valid_reference_count": 0,
            },
            abstained=True,
            message=support_message,
            provider_status={
                "generation": "not_called",
                "keyword": "not_called",
                "hybrid": "not_called",
                "fallback_used": False,
            },
            stage_latency=self._complete_timings({}, total_started),
            scope=self.scope.scope_id,
            partition=self.scope.partition_name,
            quality_status=quality_status,
            answer_boundary={
                "confirmed_evidence": [],
                "possible_explanations": [],
                "recommended_checks": [],
                "safety_warnings": response_safety_notes,
                "clarifying_question": None,
                "insufficient_evidence_notice": support_message,
                "hypotheses_promoted_to_fact": False,
                "unsupported_repair_instructions": 0,
            },
            diagnostics={"scope_expanded": False, "external_provider_called": False},
        )
        started = time.perf_counter()
        self._persist_qa_record(response, payload, signals)
        response.stage_latency["qa_persistence_ms"] = self._elapsed(started)
        response.stage_latency["total_ms"] = self._elapsed(total_started)
        return response

    def _unsafe_request_response(
        self,
        payload: QueryAwareSearchRequest,
        *,
        query: str,
        reason: str,
        total_started: float,
    ) -> QueryAwareSearchResponse:
        warning = "该请求涉及危险带电操作、安全保护绕过或虚构检修信息，系统已拒绝提供执行步骤。"
        return self._unsupported_scope_response(
            payload,
            query=query,
            reason=reason,
            total_started=total_started,
            confidence_status="UNSAFE_REQUEST_REJECTED",
            answer_message=warning,
            safety_notes=[
                "请先停机并隔离交直流电源，执行验电、放电和防误送电措施。",
                "应由具备资质的人员依据华为正式手册和现场安全规程处理。",
            ],
            diagnostic_key="unsafe_request_reason",
            quality_status="HUAWEI_SUN2000_UNSAFE_REQUEST_REJECTED",
        )

    @staticmethod
    def _answer_payload(bundle: UnderstandingBundle) -> RetrievalQueryRequest:
        return RetrievalQueryRequest(
            question=bundle.understanding.normalized_query,
            manufacturer="huawei",
            product_series="SUN2000",
            device_type="pv_inverter",
            fault_type=bundle.signals.fault_type,
            alarm_code=bundle.signals.alarm_code,
            retrieval_mode="keyword",
            enable_vector=False,
            enable_kg_enhancement=False,
        )

    @staticmethod
    def _answer_keywords(bundle: UnderstandingBundle) -> list[str]:
        specific_values = [
            *bundle.understanding.alarm_codes,
            *bundle.understanding.alarm_names,
            *bundle.understanding.symptoms,
            *bundle.understanding.components,
        ]
        values = [
            *specific_values,
            *QuerySignalExtractionService.retrieval_terms(bundle.understanding.normalized_query, limit=48),
            *bundle.understanding.device_models,
            bundle.signals.product_family,
            "华为",
            "SUN2000",
        ]
        return list(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))

    @staticmethod
    def _retain_signal_supported_candidates(candidates: list[QueryAwareCandidate], signals) -> list[QueryAwareCandidate]:
        output: list[QueryAwareCandidate] = []
        specific_model = signals.model if signals.model and signals.model.upper() != "SUN2000" else None
        fault_terms = QuerySignalExtractionService.CANONICAL_SYMPTOMS_BY_FAULT.get(signals.fault_type or "", ())
        for item in candidates:
            if specific_model and not item.exact_model_match:
                continue
            if signals.alarm_code:
                if not item.exact_alarm_match:
                    continue
            elif fault_terms:
                text = " ".join((
                    item.document_title or "", item.section_title or "", item.content or "",
                )).casefold()
                compact_text = "".join(character for character in text if character.isalnum())
                if not any(
                    "".join(character for character in term.casefold() if character.isalnum()) in compact_text
                    for term in fault_terms
                ):
                    continue
            output.append(item)
        return output

    @staticmethod
    def _answer_chunks(candidates: list[QueryAwareCandidate], valid_ids: set[str]) -> list[RetrievedChunk]:
        output: list[RetrievedChunk] = []
        for item in candidates:
            if item.chunk_id not in valid_ids:
                continue
            chunk = item.chunk
            document = item.document
            source_channels = set(item.source_channels)
            retrieval_source = (
                "hybrid"
                if any("KEYWORD" in value for value in source_channels) and "RAW_VECTOR" in source_channels
                else "vector" if "RAW_VECTOR" in source_channels else "keyword"
            )
            output.append(RetrievedChunk(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                chunk_index=chunk.chunk_index,
                section_title=chunk.section_title,
                page_number=chunk.page_number,
                content=chunk.content,
                score=round(float(item.final_score), 6),
                manufacturer=document.manufacturer,
                product_series=document.product_series,
                device_type=document.device_type,
                document_type=document.document_type,
                source=document.source,
                created_at=chunk.created_at,
                keyword_score=round(float(item.final_score), 6) if retrieval_source != "vector" else None,
                vector_score=round(float(item.final_score), 6) if retrieval_source != "keyword" else None,
                rrf_score=round(float(item.rrf_score), 8),
                rerank_score=item.rerank_score,
                final_score=round(float(item.final_score), 8),
                exact_model_boost=1.0 if item.exact_model_match else 0.0,
                exact_fault_code_boost=1.0 if item.exact_alarm_match else 0.0,
                filter_summary={"scope_id": HUAWEI_SUN2000_COMPETITION_SCOPE_ID},
                retrieval_source=retrieval_source,
            ))
        return output

    def _trace_id(self, request_id: str | None) -> str:
        if request_id:
            material = f"{self.current_user.id}:{request_id}".encode("utf-8")
            return f"qa_req_{hashlib.sha256(material).hexdigest()[:32]}"
        return f"qa_query_{uuid4().hex}"

    def rerank_by_chunk_ids(self, query: str, chunk_ids: list[str], *, enable_llm: bool, allow_real_api: bool) -> dict:
        parsed = [UUID(value) for value in chunk_ids]
        rows = list(self.db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
            KnowledgeChunk.id.in_(parsed),
            *RetrievalRepository._scope_filters(self.scope),
        )))
        by_id = {str(chunk.id): (chunk, document) for chunk, document in rows}
        bundle = self.understand(query, enable_llm=enable_llm, allow_real_api=allow_real_api)
        candidates = []
        for rank, value in enumerate(chunk_ids, start=1):
            if value not in by_id:
                continue
            chunk, document = by_id[value]
            candidate = QueryAwareCandidate(
                candidate_id=value, chunk_id=value, document_id=str(document.id), document_title=document.title,
                content=chunk.content, section_title=chunk.section_title, page_number=chunk.page_number,
                chunk=chunk, document=document, source_channels={"SUPPLIED_CANDIDATE"},
                source_query_types={"ORIGINAL"}, raw_ranks={"SUPPLIED_CANDIDATE": rank},
                rrf_score=round(1 / (60 + rank), 8), final_score=round(1 / (60 + rank), 8),
                source_chunk_ids=[value], source_locator=(chunk.metadata_json or {}).get("source_locator") or {},
                scope_validation_passed=True,
            )
            candidates.append(candidate)
        pre_guard = PreRerankHardGuardService().apply(candidates, understanding=bundle.understanding)
        deterministic = DeterministicEvidenceRerankService().rerank(
            pre_guard.candidates, understanding=bundle.understanding,
        )
        dedicated = DedicatedRerankService().rerank(
            pre_guard.candidates,
            understanding=bundle.understanding,
            allow_real_api=allow_real_api,
            fallback_candidates=deterministic.candidates,
        )
        if dedicated.diagnostics.get("success"):
            post_constraints = PostRerankConstraintService().apply(
                dedicated.candidates, understanding=bundle.understanding,
            )
        else:
            post_constraints = PostRerankConstraintResult(
                dedicated.candidates,
                {
                    "executed": False,
                    "status": "SKIPPED_TO_PRESERVE_DETERMINISTIC_FALLBACK_ORDER",
                    "fallback": True,
                    "candidate_additions": 0,
                    "candidate_removals": 0,
                    "source_modifications": 0,
                    "citation_modifications": 0,
                },
            )
        return {
            "eligible": bool(pre_guard.candidates),
            "executed": dedicated.diagnostics.get("success", False),
            "fallback": dedicated.diagnostics.get("fallback", False),
            "candidate_additions": 0,
            "candidate_source_modifications": 0,
            "candidates": [self._read(item).model_dump(mode="json") for item in post_constraints.candidates],
            "diagnostics": {
                "pre_rerank_hard_guard": pre_guard.diagnostics,
                "deterministic_rerank": deterministic.diagnostics,
                "dedicated_rerank": dedicated.diagnostics,
                "post_rerank_constraints": post_constraints.diagnostics,
                "minimax_tiebreak": {"called": False, "skipped_reason": "NOT_IN_RANKING_PATH"},
            },
        }

    @staticmethod
    def _refine(candidates: list[QueryAwareCandidate], *, top_k: int) -> list[QueryAwareCandidate]:
        surfaced: list[QueryAwareCandidate] = []
        sections: set[tuple[str, str]] = set()
        content_keys: set[str] = set()
        per_document: dict[str, int] = {}
        for item in candidates:
            section_key = (item.document_id, item.section_title or f"page:{item.page_number}")
            content_key = hashlib.sha256("".join(item.content.split()).lower()[:320].encode("utf-8")).hexdigest()
            if section_key in sections or content_key in content_keys or per_document.get(item.document_id, 0) >= 2:
                continue
            if not item.scope_validation_passed:
                continue
            surfaced.append(item)
            sections.add(section_key)
            content_keys.add(content_key)
            per_document[item.document_id] = per_document.get(item.document_id, 0) + 1
            if len(surfaced) >= top_k:
                break
        return surfaced

    @staticmethod
    def _require_page_locators(citation: CitationValidationResult, candidates: list[QueryAwareCandidate]) -> CitationValidationResult:
        missing = [item.chunk_id for item in candidates if item.page_number is None or not (item.section_title or item.source_locator)]
        if missing:
            citation.citation_valid = False
            citation.citation_coverage = round(max(0.0, (len(candidates) - len(missing)) / max(1, len(candidates))), 4)
            citation.invalid_reference_ids.extend(missing)
            citation.invalid_reference_reasons.update({value: "missing_page_or_section_locator" for value in missing})
        return citation

    @classmethod
    def _read(cls, item: QueryAwareCandidate) -> QueryAwareCandidateRead:
        return QueryAwareCandidateRead(
            candidate_id=item.candidate_id,
            chunk_id=item.chunk_id,
            document_id=item.document_id,
            document_title=item.document_title,
            section_title=item.section_title,
            page_number=item.page_number,
            source_channels=sorted(item.source_channels),
            source_query_types=sorted(item.source_query_types),
            raw_ranks=dict(sorted(item.raw_ranks.items())),
            raw_scores={key: round(value, 8) for key, value in sorted(item.raw_scores.items())},
            rrf_score=item.rrf_score,
            rerank_score=item.rerank_score,
            final_score=item.final_score,
            exact_model_match=item.exact_model_match,
            exact_alarm_match=item.exact_alarm_match,
            semantic_unit_id=item.semantic_unit_id,
            source_chunk_ids=item.source_chunk_ids,
            source_locator=item.source_locator,
            scope_validation_passed=item.scope_validation_passed,
            evidence_identity=item.evidence_identity,
            evidence_level=item.evidence_level,
            requested_information_support=sorted(item.requested_information_support),
            requested_information_coverage=item.requested_information_coverage,
            direct_answer_score=item.direct_answer_score,
            direct_answer_level=item.direct_answer_level,
            generality_penalty=item.generality_penalty,
            quote=cls._quote(item.content),
        )

    @staticmethod
    def _quote(content: str) -> str:
        return " ".join((content or "").split())[:240]

    @staticmethod
    def _prefetch_query_embedding(query: str) -> tuple[list[float], float]:
        started = time.perf_counter()
        settings = get_settings()
        result = EmbeddingService(allow_real_api=True).embed_texts(
            [query], provider=settings.EMBEDDING_PROVIDER,
        )
        return result.vectors[0], round((time.perf_counter() - started) * 1000, 3)

    @staticmethod
    def _elapsed(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)

    @classmethod
    def _complete_timings(cls, values: dict[str, float], total_started: float) -> dict[str, float]:
        defaults = (
            "signal_extraction_ms", "question_completeness_ms", "query_understanding_ms", "retrieval_plan_ms",
            "keyword_ms", "embedding_ms", "raw_vector_ms", "semantic_unit_ms", "fusion_ms", "rerank_ms",
            "pre_rerank_guard_ms", "deterministic_rerank_ms", "dedicated_rerank_ms",
            "post_rerank_constraint_ms", "tiebreak_ms", "refinement_ms", "citation_ms", "confidence_ms",
            "answer_generation_ms", "qa_persistence_ms",
        )
        output = {key: round(float(values.get(key) or 0.0), 3) for key in defaults}
        output["total_ms"] = cls._elapsed(total_started)
        return output

    @staticmethod
    def _model_routing(understanding: QueryUnderstandingResult, dedicated: dict[str, Any]) -> dict[str, Any]:
        return {
            "query_understanding_requested_provider": understanding.requested_provider,
            "query_understanding_actual_provider": understanding.actual_provider,
            "dedicated_rerank_requested_provider": get_settings().RAG_DEDICATED_RERANK_PROVIDER,
            "dedicated_rerank_actual_provider": (
                dedicated.get("provider") if dedicated.get("success") else "deterministic_rerank_v2"
            ),
            "minimax_ranking_path": False,
        }

    @staticmethod
    def _minimax_diagnostics(
        understanding: QueryUnderstandingResult,
        tiebreak: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        settings = get_settings()
        qu = understanding.structured_model_diagnostics or {}
        tie = tiebreak or {}
        return {
            "enabled": settings.MINIMAX_ENABLED,
            "model": settings.MINIMAX_MODEL,
            "protocol": settings.MINIMAX_PROTOCOL,
            "thinking_enabled": settings.MINIMAX_THINKING_TYPE != "disabled",
            "service_tier": settings.MINIMAX_SERVICE_TIER,
            "tool_call_used": bool((qu.get("tool_call_count") or 0) == 1 or tie.get("tool_call_used")),
            "structured_success": bool(qu.get("success") or tie.get("structured_success")),
            "fallback": bool(understanding.provider_fallback or tie.get("provider_fallback")),
            "fallback_reason": understanding.provider_fallback_reason or tie.get("fallback_reason"),
            "circuit_breaker_state": {
                "query_understanding": understanding.circuit_breaker_state,
                "tiebreak": tie.get("circuit_breaker_state", "CLOSED"),
            },
            "latency_ms": round(float(qu.get("latency_ms") or 0.0) + float(tie.get("latency_ms") or 0.0), 3),
            "trace_id": qu.get("trace_id") or tie.get("trace_id"),
        }

    @staticmethod
    def _public_rerank_diagnostics(value: dict[str, Any]) -> dict[str, Any]:
        breakdown = value.get("score_breakdown") or {}
        return {
            "weights_version": value.get("weights_version"),
            "candidates_in": value.get("candidates_in", 0),
            "candidates_out": value.get("candidates_out", 0),
            "order_changed": value.get("order_changed", False),
            "score_breakdown_summary": {
                "scored": len(breakdown),
                "protected": sum(
                    "EXACT_ENTITY_VALID_CITATION_PROTECTED" in (item.get("reason_codes") or [])
                    for item in breakdown.values()
                ),
                "conflicts": sum(bool(item.get("conflict_penalty")) for item in breakdown.values()),
            },
        }

    @staticmethod
    def _public_tiebreak_diagnostics(value: dict[str, Any]) -> dict[str, Any]:
        allowed = (
            "eligible", "called", "skipped_reason", "candidates_in", "candidates_out", "structured_success",
            "order_changed", "fallback_order_preserved",
        )
        return {key: value.get(key) for key in allowed}

    @staticmethod
    def _public_dedicated_rerank_diagnostics(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "used": bool(value.get("success")),
            "provider": value.get("provider"),
            "provider_status": value.get("provider_status"),
            "model": value.get("model"),
            "instruct_version": value.get("instruct_version"),
            "fallback": bool(value.get("fallback")),
            "fallback_reason": value.get("fallback_reason"),
            "latency_ms": value.get("latency_ms", 0.0),
            "cache_hit": bool(value.get("cache_hit")),
            "circuit_breaker_state": value.get("circuit_breaker_state", "CLOSED"),
            "candidates_in": value.get("candidates_in", 0),
            "candidates_out": value.get("candidates_out", 0),
            "rankings": value.get("rankings") or [],
        }
