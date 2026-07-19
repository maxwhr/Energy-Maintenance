from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User
from app.schemas.retrieval_plan import RetrievalPlan, RetrievalQueryVariant
from app.services.citation_validation_service import CitationValidationService
from app.services.cross_modal_retrieval_plan_service import CrossModalRetrievalPlan
from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from app.services.multi_query_retrieval_service import MultiQueryRetrievalService
from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.rrf_fusion_service import RRFFusionService


@dataclass(slots=True)
class CrossModalRetrievalResult:
    generated_queries: list[dict]
    requested_channels: list[str]
    actual_channels: list[str]
    raw_candidates: list[dict]
    surfaced_results: list[dict]
    citations: list[dict]
    citation_validity_ratio: float
    citation_coverage_ratio: float
    confidence_status: str
    stage_latency: dict[str, float]
    rrf_vote_breakdown: dict = field(default_factory=dict)
    deterministic_rerank: dict = field(default_factory=dict)
    dedicated_rerank: dict = field(default_factory=lambda: {
        "used": False,
        "status": "DEFERRED_QWEN3_RERANK_CONFIG",
        "external_calls": 0,
    })
    external_call_counts: dict = field(default_factory=lambda: {
        "embedding": 0, "dashvector": 0, "qwen3_rerank": 0, "cloud_llm": 0,
    })

    def as_dict(self) -> dict:
        return asdict(self)


class CrossModalRetrievalService:
    """Run source-faithful multimodal queries through deterministic Pilot retrieval."""

    CHANNELS = ["EXACT_KEYWORD", "SCOPED_KEYWORD", "KG_ALIAS"]
    TYPE_MAP = {
        "ORIGINAL_TEXT": "ORIGINAL",
        "OCR_ENTITY_QUERY": "CANONICAL",
        "VISUAL_SYMPTOM_QUERY": "SYMPTOM_QUERY",
        "ALARM_QUERY": "REQUEST_QUERY",
        "ACTION_OR_SAFETY_QUERY": "REQUEST_QUERY",
    }

    def __init__(self, db: Session, *, current_user: User):
        self.db = db
        self.current_user = current_user
        self.query_aware = QueryAwareRetrievalService(db, current_user=current_user)
        self.scope = self.query_aware.scope

    def retrieve(self, plan: CrossModalRetrievalPlan, *, top_k: int = 5) -> CrossModalRetrievalResult:
        total_started = time.perf_counter()
        if plan.scope_id != self.scope.scope_id:
            raise ValueError("cross-modal retrieval scope mismatch")
        if not plan.queries or plan.queries[0].query_type != "ORIGINAL_TEXT":
            raise ValueError("cross-modal plan must retain ORIGINAL_TEXT first")
        if plan.resolved_device_model and not plan.resolved_product_family:
            return self._unsupported_entity_result(plan, total_started, "UNSUPPORTED_DEVICE_MODEL_SCOPE")

        understanding_started = time.perf_counter()
        combined = "；".join(item.query for item in plan.queries)
        bundle = self.query_aware.understand(combined, enable_llm=False, allow_real_api=False)
        understanding_ms = self._elapsed(understanding_started)
        variants = [RetrievalQueryVariant(
            variant_type=self.TYPE_MAP[item.query_type],
            query=item.query,
            hypothesis=bool(item.hypothesis_signals),
            purpose="multimodal evidence-derived source-faithful retrieval",
        ) for item in plan.queries]
        channels = list(self.CHANNELS)
        internal_plan = RetrievalPlan(
            original_query=plan.original_query,
            canonical_query=plan.queries[1].query if len(plan.queries) > 1 else plan.original_query,
            query_variants=variants,
            requested_channels=channels,
            channel_queries={channel: [item.query for item in variants] for channel in channels},
            channel_weights={"EXACT_KEYWORD": 1.20, "SCOPED_KEYWORD": 1.0, "KG_ALIAS": 0.85},
            query_weights={"ORIGINAL": 1.0, "CANONICAL": 0.95, "SYMPTOM_QUERY": 0.82, "REQUEST_QUERY": 0.86},
            anchor_types=[],
            channel_candidate_budgets={channel: 50 for channel in channels},
            per_channel_identity_limit=60,
            fusion_candidate_limit=150,
            candidate_top_k=50,
            rerank_required=True,
            required_scope=self.scope.scope_id,
            fallback_policy="KEEP_SCOPE_AND_PRESERVE_RRF_WITHOUT_QWEN3",
        )

        retrieval_started = time.perf_counter()
        retrieval = MultiQueryRetrievalService(allow_real_api=False).retrieve(
            plan=internal_plan,
            understanding=bundle.understanding,
            scope=self.scope,
        )
        retrieval_ms = self._elapsed(retrieval_started)
        fusion_started = time.perf_counter()
        rrf = RRFFusionService()
        fused = rrf.fuse(
            retrieval.rankings,
            top_k=internal_plan.fusion_candidate_limit,
            channel_weights=internal_plan.channel_weights,
            query_weights=internal_plan.query_weights,
        )
        fusion_ms = self._elapsed(fusion_started)
        raw_candidates = [self._candidate(item) for item in fused[:50]]

        citation_started = time.perf_counter()
        pre_citation = CitationValidationService(self.db).validate(
            [{"chunk_id": item.chunk_id} for item in fused],
            candidate_chunk_ids={UUID(item.chunk_id) for item in fused},
            scope=self.scope,
        )
        citation_status = {item.chunk_id: item.chunk_id in set(pre_citation.valid_reference_ids) for item in fused}
        citation_pre_ms = self._elapsed(citation_started)

        guard_started = time.perf_counter()
        guarded = PreRerankHardGuardService().apply(fused, understanding=bundle.understanding)
        guard_ms = self._elapsed(guard_started)
        rerank_started = time.perf_counter()
        reranked = DeterministicEvidenceRerankService().rerank(
            guarded.candidates,
            understanding=bundle.understanding,
            citation_status=citation_status,
        )
        rerank_ms = self._elapsed(rerank_started)
        refinement_started = time.perf_counter()
        surfaced = ResultSetRefinementService().refine_query_aware(
            reranked.candidates,
            requested_top_k=top_k,
        ).surfaced
        refinement_ms = self._elapsed(refinement_started)

        citation_started = time.perf_counter()
        citation = CitationValidationService(self.db).validate(
            [{"chunk_id": item.chunk_id} for item in surfaced],
            candidate_chunk_ids={UUID(item.chunk_id) for item in surfaced},
            scope=self.scope,
        )
        valid_ids = set(citation.valid_reference_ids)
        citations = [self._citation(item) for item in surfaced if item.chunk_id in valid_ids]
        citation_ms = self._elapsed(citation_started)
        validity = float(citation.citation_validity_ratio)
        coverage = float(citation.citation_coverage_ratio)
        confidence_status = "SUPPORTED" if citations and validity >= 0.98 and coverage >= 0.95 else (
            "INSUFFICIENT_EVIDENCE" if not citations else "PARTIAL"
        )
        stage_latency = {
            "understanding_ms": understanding_ms,
            "retrieval_ms": retrieval_ms,
            "fusion_ms": fusion_ms,
            "pre_citation_ms": citation_pre_ms,
            "hard_guard_ms": guard_ms,
            "deterministic_rerank_ms": rerank_ms,
            "refinement_ms": refinement_ms,
            "citation_ms": citation_ms,
            "total_ms": self._elapsed(total_started),
        }
        return CrossModalRetrievalResult(
            generated_queries=[{
                "query_type": item.query_type,
                "query": item.query,
                "evidence_ids": item.evidence_ids,
                "hypothesis_signals": item.hypothesis_signals,
            } for item in plan.queries],
            requested_channels=channels,
            actual_channels=retrieval.actual_channels,
            raw_candidates=raw_candidates,
            surfaced_results=[self._candidate(item) for item in surfaced],
            citations=citations,
            citation_validity_ratio=validity,
            citation_coverage_ratio=coverage,
            confidence_status=confidence_status,
            stage_latency=stage_latency,
            rrf_vote_breakdown=rrf.last_diagnostics,
            deterministic_rerank=reranked.diagnostics,
        )

    def _unsupported_entity_result(
        self,
        plan: CrossModalRetrievalPlan,
        total_started: float,
        reason: str,
    ) -> CrossModalRetrievalResult:
        return CrossModalRetrievalResult(
            generated_queries=[{
                "query_type": item.query_type,
                "query": item.query,
                "evidence_ids": item.evidence_ids,
                "hypothesis_signals": item.hypothesis_signals,
            } for item in plan.queries],
            requested_channels=list(self.CHANNELS),
            actual_channels=[],
            raw_candidates=[],
            surfaced_results=[],
            citations=[],
            citation_validity_ratio=1.0,
            citation_coverage_ratio=1.0,
            confidence_status="INSUFFICIENT_EVIDENCE",
            stage_latency={
                "scope_guard_ms": self._elapsed(total_started),
                "total_ms": self._elapsed(total_started),
            },
            deterministic_rerank={
                "status": "SKIPPED_UNSUPPORTED_ENTITY_SCOPE",
                "reason": reason,
                "candidate_additions": 0,
                "candidate_source_modifications": 0,
            },
        )

    @staticmethod
    def _candidate(item) -> dict:
        return {
            "candidate_id": item.candidate_id,
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "document_title": item.document_title,
            "section_title": item.section_title,
            "page_number": item.page_number,
            "source_channels": sorted(item.source_channels),
            "source_query_types": sorted(item.source_query_types),
            "rrf_score": item.rrf_score,
            "rerank_score": item.rerank_score,
            "final_score": item.final_score,
            "source_locator": item.source_locator,
            "scope_validation_passed": item.scope_validation_passed,
            "quote": CrossModalRetrievalService._quote(item.content),
        }

    @staticmethod
    def _citation(item) -> dict:
        return {
            "citation_id": f"citation:{item.chunk_id}",
            "chunk_id": item.chunk_id,
            "document_id": item.document_id,
            "document_title": item.document_title,
            "section_title": item.section_title,
            "page_number": item.page_number,
            "source_locator": item.source_locator,
            "quote": CrossModalRetrievalService._quote(item.content),
            "source_type": "OFFICIAL_KNOWLEDGE",
        }

    @staticmethod
    def _quote(value: str, limit: int = 360) -> str:
        return " ".join((value or "").split())[:limit]

    @staticmethod
    def _elapsed(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)
