from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class DraftBoundaryDecision:
    allowed: bool
    artifact_type: str
    blocked_reasons: list[str]
    requires_human_approval: bool = True
    formal_record_created: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultimodalSopTaskBoundaryService:
    def allow_sop_draft(
        self,
        *,
        device_model: str | None,
        user_confirmed_device: bool,
        valid_citation_count: int,
        safety_complete: bool,
        evidence_confidence: float,
        open_high_conflicts: int,
    ) -> DraftBoundaryDecision:
        reasons = []
        if not device_model or (not user_confirmed_device and evidence_confidence < 0.85):
            reasons.append("device_model_not_confirmed")
        if valid_citation_count < 1:
            reasons.append("valid_citation_required")
        if not safety_complete:
            reasons.append("safety_prerequisites_incomplete")
        if evidence_confidence < 0.70:
            reasons.append("evidence_confidence_below_threshold")
        if open_high_conflicts:
            reasons.append("unresolved_high_risk_conflict")
        return DraftBoundaryDecision(not reasons, "sop_draft", reasons)

    def allow_task_draft(
        self,
        *,
        sop_status: str,
        sop_user_confirmed: bool,
        safety_complete: bool,
        role: str,
    ) -> DraftBoundaryDecision:
        reasons = []
        if sop_status != "approved" and not sop_user_confirmed:
            reasons.append("approved_or_user_confirmed_sop_required")
        if not safety_complete:
            reasons.append("safety_prerequisites_incomplete")
        if role not in {"engineer", "expert", "admin"}:
            reasons.append("role_not_allowed")
        return DraftBoundaryDecision(not reasons, "task_draft", reasons)
