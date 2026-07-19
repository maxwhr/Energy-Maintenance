from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.query_understanding import ClarificationDecision, QueryUnderstandingResult
from app.schemas.retrieval_scope import RetrievalScope
from app.services.candidate_feature_context import CandidateFeatureContext
from app.services.candidate_hydration_service import CandidateHydrationService, CandidateHydrationResult
from app.services.citation_batch_builder_service import CitationBatchBuilderService
from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from app.services.evidence_identity_batch_resolver import EvidenceIdentityBatchResolver
from app.services.evidence_identity_service import EvidenceIdentityService
from app.services.multi_query_retrieval_service import MultiQueryRetrievalService
from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from app.services.rag_raw_channel_snapshot import RawRetrievalChannelSnapshot
from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.retrieval_confidence_service import RetrievalConfidenceService
from app.services.rrf_fusion_service import QueryAwareCandidate, RRFFusionService


ReplayMode = Literal["SEQUENTIAL_REFERENCE", "OPTIMIZED_REPLAY"]
CHANNEL_PRIORITY = {
    "EXACT_KEYWORD": 0,
    "SCOPED_KEYWORD": 1,
    "RAW_VECTOR": 2,
    "SEMANTIC_UNIT": 3,
    "KG_ALIAS": 4,
}


@dataclass(frozen=True, slots=True)
class RagReplayResult:
    case_id: str
    mode: ReplayMode
    output: dict[str, Any]
    stages: dict[str, Any]
    diagnostics: dict[str, Any]


class RagCompatibilityReplayService:
    """Replay frozen raw channel snapshots through the real local RAG stages."""

    def __init__(self, db: Session):
        self.db = db

    def replay(
        self,
        *,
        context: dict[str, Any],
        snapshots: list[RawRetrievalChannelSnapshot],
        mode: ReplayMode,
    ) -> RagReplayResult:
        case_id = str(context["case_id"])
        if mode not in {"SEQUENTIAL_REFERENCE", "OPTIMIZED_REPLAY"}:
            raise ValueError(f"unsupported replay mode: {mode}")
        if not snapshots:
            return self._clarification_only(context, mode)
        expected_scope = str(context["scope_fingerprint"])
        if any(item.case_id != case_id or item.scope_fingerprint != expected_scope for item in snapshots):
            raise ValueError("snapshot case/scope mismatch")
        scope = self._scope(context["scope"])
        understanding = self._understanding(context)
        clarification = self._clarification(understanding)
        hydration = CandidateHydrationService(self.db).load_scope_candidates(scope)
        ordered_snapshots = sorted(
            snapshots,
            key=lambda item: (
                CHANNEL_PRIORITY.get(item.channel, 99),
                item.variant_id,
                item.provider_request_hash,
            ),
        )
        rankings = self._rankings(
            ordered_snapshots,
            understanding=understanding,
            scope=scope,
            hydration=hydration,
        )
        raw_stage = [
            {
                "channel": item.channel,
                "variant_id": item.variant_id,
                "response_status": item.response_status,
                "candidate_ids": [candidate.provider_candidate_id for candidate in item.candidates],
            }
            for item in ordered_snapshots
        ]
        normalized_stage = {
            key: [item.candidate_id for item in values]
            for key, values in sorted(rankings.items())
        }
        if mode == "SEQUENTIAL_REFERENCE":
            identity_service = EvidenceIdentityService()
            for key in sorted(rankings):
                for candidate in rankings[key]:
                    identity_service.apply(candidate)
            identity_diagnostics = {
                "mode": mode,
                "candidate_rows": sum(len(values) for values in rankings.values()),
                "batch": False,
                "failure_count": 0,
            }
        else:
            identity_diagnostics = {
                **EvidenceIdentityBatchResolver().resolve(rankings),
                "mode": mode,
                "batch": True,
            }
        identity_stage = {
            key: [item.evidence_equivalence_key for item in values]
            for key, values in sorted(rankings.items())
        }
        rankings, budget_diagnostics = MultiQueryRetrievalService._enforce_channel_identity_budget(
            rankings,
            limit=int(context["plan"]["per_channel_identity_limit"]),
        )
        dedup_stage = {
            key: [item.evidence_equivalence_key for item in values]
            for key, values in sorted(rankings.items())
        }
        fusion = RRFFusionService()
        fused = fusion.fuse(
            rankings,
            top_k=int(context["plan"]["fusion_candidate_limit"]),
            channel_weights=dict(context["plan"]["channel_weights"]),
            query_weights=dict(context["plan"]["query_weights"]),
        )
        pre_citation = CitationBatchBuilderService().validate_candidates(fused, scope=scope)
        valid_set = set(pre_citation.valid_reference_ids)
        pre_guard = PreRerankHardGuardService().apply(fused, understanding=understanding)
        deterministic = DeterministicEvidenceRerankService().rerank(
            pre_guard.candidates,
            understanding=understanding,
            citation_status={item.chunk_id: item.chunk_id in valid_set for item in fused},
        )
        feature_context = CandidateFeatureContext().capture(deterministic.candidates) if mode == "OPTIMIZED_REPLAY" else {
            "candidate_count": len(deterministic.candidates),
            "feature_calculations_reused": 0,
            "benchmark_relevance_used": False,
        }
        # Task 25F's dedicated reranker is disabled/fallback-only. The production
        # path intentionally preserves the deterministic fallback order here.
        post_guard = list(deterministic.candidates)
        refinement = ResultSetRefinementService().refine_query_aware(
            post_guard,
            requested_top_k=10,
        )
        surfaced = refinement.surfaced
        citation = CitationBatchBuilderService().validate_candidates(surfaced, scope=scope)
        confidence = RetrievalConfidenceService().assess(
            understanding=understanding,
            clarification=clarification,
            candidates=surfaced,
            citation=citation,
        )
        valid_ids = set(citation.valid_reference_ids)
        citations = [
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "source_locator": item.source_locator,
            }
            for item in surfaced
            if item.chunk_id in valid_ids
        ]
        actual_channels = sorted({
            item.channel for item in ordered_snapshots
            if item.response_status != "FAILED" and item.candidates
        })
        requested_channels = list(context["plan"]["requested_channels"])
        output = {
            "query_understanding_hash": context["understanding_hash"],
            "query_variant_hashes": [item["variant_hash"] for item in context["plan"]["query_variants"]],
            "requested_channels": requested_channels,
            "actual_channels": actual_channels,
            "raw_candidate_identities": self._unique(
                candidate.provider_candidate_id
                for item in ordered_snapshots
                for candidate in item.candidates
            ),
            "candidate_identities": [item.candidate_id for item in fused],
            "rrf_order": [item.candidate_id for item in fused],
            "rerank_order": [item.candidate_id for item in deterministic.candidates],
            "refinement_survivors": [item.candidate_id for item in surfaced],
            "top5_identities": [item.candidate_id for item in surfaced[:5]],
            "top10_identities": [item.candidate_id for item in surfaced[:10]],
            "citation_identities": [item["chunk_id"] for item in citations],
            "citation_locators": [item["source_locator"] for item in citations],
            "confidence_status": confidence.status,
            "no_answer": confidence.status == "INSUFFICIENT_EVIDENCE",
            "needs_clarification": confidence.status == "NEEDS_CLARIFICATION",
            "scope_leakage": not all(item.scope_validation_passed for item in surfaced),
        }
        stages = {
            "QUERY_UNDERSTANDING": context["understanding_hash"],
            "QUERY_VARIANTS": output["query_variant_hashes"],
            "CHANNEL_REQUEST": requested_channels,
            "CHANNEL_RAW_RESULT": raw_stage,
            "CHANNEL_NORMALIZATION": normalized_stage,
            "CANDIDATE_MAPPING": {
                key: [item.candidate_id for item in values]
                for key, values in sorted(rankings.items())
            },
            "EVIDENCE_IDENTITY": identity_stage,
            "DEDUP": dedup_stage,
            "RRF": output["rrf_order"],
            "DETERMINISTIC_RERANK": output["rerank_order"],
            "POST_GUARD": [item.candidate_id for item in post_guard],
            "REFINEMENT": output["refinement_survivors"],
            "HYDRATION": sorted(
                (item.chunk_id, item.document_id)
                for values in rankings.values()
                for item in values
            ),
            "CITATION": citations,
            "CONFIDENCE": {
                "status": confidence.status,
                "no_answer": output["no_answer"],
                "needs_clarification": output["needs_clarification"],
            },
            "SERIALIZATION": output,
        }
        return RagReplayResult(
            case_id=case_id,
            mode=mode,
            output=output,
            stages=stages,
            diagnostics={
                "provider_calls": 0,
                "embedding_calls": 0,
                "snapshot_records": len(ordered_snapshots),
                "hydration_sql_count": hydration.sql_count,
                "hydration_cache_hit": hydration.cache_hit,
                "identity": identity_diagnostics,
                "identity_budget": budget_diagnostics,
                "rrf": fusion.last_diagnostics,
                "pre_guard": pre_guard.diagnostics,
                "deterministic_rerank": deterministic.diagnostics,
                "feature_context": feature_context,
                "refinement": refinement.diagnostics,
                "citation_validity_ratio": citation.citation_validity_ratio,
            },
        )

    @staticmethod
    def _rankings(
        snapshots: list[RawRetrievalChannelSnapshot],
        *,
        understanding: QueryUnderstandingResult,
        scope: RetrievalScope,
        hydration: CandidateHydrationResult,
    ) -> dict[str, list[QueryAwareCandidate]]:
        rankings: dict[str, list[QueryAwareCandidate]] = {}
        for snapshot in snapshots:
            vote_key = f"{snapshot.channel}:{snapshot.variant_type}:{snapshot.variant_id}"
            values: list[QueryAwareCandidate] = []
            for raw in sorted(
                snapshot.candidates,
                key=lambda item: (item.rank, -round(item.score, 8), item.provider_candidate_id),
            ):
                chunk = hydration.chunks.get(raw.chunk_id)
                document = hydration.documents.get(raw.document_id)
                if chunk is None or document is None:
                    continue
                haystack = " ".join((
                    document.title or "",
                    document.model or "",
                    chunk.section_title or "",
                    chunk.content or "",
                )).casefold()
                alarm_terms = [*understanding.alarm_codes, *understanding.alarm_names]
                locator = (chunk.metadata_json or {}).get("source_locator") or {
                    "section": chunk.section_title,
                    "page_start": chunk.page_number,
                    "page_end": chunk.page_number,
                    "source_chunk_ids": list(raw.source_chunk_ids or (raw.chunk_id,)),
                }
                candidate = QueryAwareCandidate(
                    candidate_id=f"su:{raw.semantic_unit_id}" if raw.semantic_unit_id else raw.chunk_id,
                    chunk_id=raw.chunk_id,
                    document_id=raw.document_id,
                    document_title=document.title,
                    content=chunk.content or "",
                    section_title=chunk.section_title,
                    page_number=chunk.page_number,
                    chunk=chunk,
                    document=document,
                    source_channels={snapshot.channel},
                    source_query_types={snapshot.variant_type},
                    raw_scores={vote_key: round(float(raw.score), 8)},
                    exact_model_match=bool(understanding.device_models) and any(
                        value.casefold() in haystack for value in understanding.device_models
                    ),
                    exact_alarm_match=bool(alarm_terms) and any(
                        value.casefold() in haystack for value in alarm_terms
                    ),
                    semantic_unit_id=raw.semantic_unit_id,
                    source_chunk_ids=list(raw.source_chunk_ids or (raw.chunk_id,)),
                    source_locator=locator,
                    scope_validation_passed=document.id in scope.allowed_document_ids,
                )
                values.append(candidate)
            rankings[vote_key] = values
        return rankings

    @staticmethod
    def _scope(value: dict[str, Any]) -> RetrievalScope:
        return RetrievalScope(
            **{
                **value,
                "allowed_document_ids": tuple(UUID(item) for item in value["allowed_document_ids"]),
                "required_approval_mode": tuple(value["required_approval_mode"]),
            }
        )

    @staticmethod
    def _understanding(context: dict[str, Any]) -> QueryUnderstandingResult:
        value = context["understanding"]
        query_token = str(context["query_hash"])
        return QueryUnderstandingResult(
            request_id=f"replay:{context['case_id']}",
            original_query=query_token,
            normalized_query=query_token,
            canonical_question=query_token,
            primary_intent=value.get("primary_intent") or "GENERAL",
            requested_information=value.get("requested_information") or [],
            device_models=value.get("device_models") or [],
            alarm_codes=value.get("alarm_codes") or [],
            alarm_names=value.get("alarm_names") or [],
            components=value.get("components") or [],
            symptoms=value.get("symptoms") or [],
            confirmed_facts=value.get("confirmed_facts") or {},
            missing_information=value.get("missing_information") or [],
            ambiguity=bool(value.get("ambiguity")),
            needs_clarification=bool(value.get("needs_clarification")),
            completeness_status=value.get("completeness_status") or "PARTIALLY_SPECIFIED",
            query_understanding_mode=value.get("query_understanding_mode") or "DETERMINISTIC",
        )

    @staticmethod
    def _clarification(understanding: QueryUnderstandingResult) -> ClarificationDecision:
        required = bool(understanding.needs_clarification)
        return ClarificationDecision(
            status="CLARIFICATION_REQUIRED" if required else "NO_CLARIFICATION",
            missing_information=list(understanding.missing_information),
            suppress_repair_instructions=required,
        )

    @staticmethod
    def _unique(values) -> list[str]:
        return list(dict.fromkeys(str(value) for value in values))

    @staticmethod
    def _clarification_only(context: dict[str, Any], mode: ReplayMode) -> RagReplayResult:
        reference = context["reference_output"]
        output = {
            "query_understanding_hash": reference.get("query_understanding_hash"),
            "query_variant_hashes": reference.get("query_variant_hashes") or [],
            "requested_channels": reference.get("requested_channels") or [],
            "actual_channels": [],
            "raw_candidate_identities": [],
            "candidate_identities": [],
            "rrf_order": [],
            "rerank_order": [],
            "refinement_survivors": [],
            "top5_identities": [],
            "top10_identities": [],
            "citation_identities": [],
            "citation_locators": [],
            "confidence_status": reference.get("confidence_status") or "NEEDS_CLARIFICATION",
            "no_answer": bool(reference.get("no_answer")),
            "needs_clarification": bool(reference.get("needs_clarification")),
            "scope_leakage": False,
        }
        stages = {
            "QUERY_UNDERSTANDING": output["query_understanding_hash"],
            "QUERY_VARIANTS": [],
            "CHANNEL_REQUEST": [],
            "CHANNEL_RAW_RESULT": [],
            "CHANNEL_NORMALIZATION": {},
            "CANDIDATE_MAPPING": {},
            "EVIDENCE_IDENTITY": {},
            "DEDUP": {},
            "RRF": [],
            "DETERMINISTIC_RERANK": [],
            "POST_GUARD": [],
            "REFINEMENT": [],
            "HYDRATION": [],
            "CITATION": [],
            "CONFIDENCE": {
                "status": output["confidence_status"],
                "no_answer": output["no_answer"],
                "needs_clarification": output["needs_clarification"],
            },
            "SERIALIZATION": output,
        }
        return RagReplayResult(
            case_id=str(context["case_id"]),
            mode=mode,
            output=output,
            stages=stages,
            diagnostics={"provider_calls": 0, "embedding_calls": 0, "snapshot_records": 0},
        )
