from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.query_understanding import ClarificationDecision, QueryUnderstandingResult
from app.services.citation_validation_service import CitationValidationResult
from app.services.rrf_fusion_service import QueryAwareCandidate


@dataclass(frozen=True, slots=True)
class RetrievalConfidenceResult:
    status: str
    confidence: float
    reason_codes: list[str]
    entity_conflicts: list[dict] = field(default_factory=list)
    evidence_conflicts: list[dict] = field(default_factory=list)


class RetrievalConfidenceService:
    def assess(
        self,
        *,
        understanding: QueryUnderstandingResult,
        clarification: ClarificationDecision,
        candidates: list[QueryAwareCandidate],
        citation: CitationValidationResult,
    ) -> RetrievalConfidenceResult:
        if clarification.status == "CLARIFICATION_REQUIRED":
            return RetrievalConfidenceResult("NEEDS_CLARIFICATION", 0.0, ["required_user_information_missing"], [], [])
        if not candidates or not citation.citation_valid:
            return RetrievalConfidenceResult("INSUFFICIENT_EVIDENCE", 0.0, ["no_valid_grounded_candidate"], [], [])
        if (understanding.alarm_codes or understanding.alarm_names) and not any(item.exact_alarm_match for item in candidates):
            return RetrievalConfidenceResult("INSUFFICIENT_EVIDENCE", 0.0, ["explicit_alarm_not_supported"], [], [])
        if understanding.device_models and not any(item.exact_model_match for item in candidates):
            return RetrievalConfidenceResult("INSUFFICIENT_EVIDENCE", 0.0, ["explicit_model_not_supported"], [], [])
        top = candidates[0].final_score
        margin = top - candidates[1].final_score if len(candidates) > 1 else top
        normalized_margin = margin / max(abs(top), 1e-9)
        explicit_models = list(dict.fromkeys(understanding.device_models))
        explicit_alarms = list(dict.fromkeys([*understanding.alarm_codes, *understanding.alarm_names]))
        entity_conflicts = []
        if len(explicit_models) > 1:
            entity_conflicts.append({"type": "device_model", "values": explicit_models})
        if len(explicit_alarms) > 1:
            entity_conflicts.append({"type": "alarm", "values": explicit_alarms})
        evidence_conflicts = []
        for item in candidates[:3]:
            metadata = item.source_locator or {}
            if metadata.get("contradiction"):
                evidence_conflicts.append({"candidate_id": item.candidate_id, "type": "explicit_contradiction"})
        close_conflicted_competition = normalized_margin < 0.08 and bool(entity_conflicts or evidence_conflicts)
        if close_conflicted_competition:
            return RetrievalConfidenceResult(
                "MULTIPLE_POSSIBILITIES",
                round(min(0.72, 0.45 + top), 4),
                ["real_entity_or_evidence_conflict", "normalized_top_candidates_close"],
                entity_conflicts,
                evidence_conflicts,
            )
        confidence = min(0.95, 0.58 + top + (0.08 if candidates[0].exact_alarm_match or candidates[0].exact_model_match else 0.0))
        return RetrievalConfidenceResult(
            "ANSWERABLE", round(confidence, 4),
            ["direct_validated_official_evidence", "multiple_documents_are_complementary_not_conflicting"],
            entity_conflicts, evidence_conflicts,
        )
