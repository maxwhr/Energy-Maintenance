from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


WORKFLOW_STAGE_ORDER = [
    "CASE_ANALYSIS",
    "EVIDENCE_REVIEW",
    "DIAGNOSIS_REVIEW",
    "SOP_DRAFT",
    "SOP_REVIEW",
    "TASK_DRAFT",
    "TASK_CREATED",
    "TASK_EXECUTION",
    "RESULT_VERIFICATION",
    "TASK_COMPLETED",
    "CORRECTION_REVIEW",
    "CLOSED",
]
WORKFLOW_STATUSES = {
    "ACTIVE",
    "WAITING_USER",
    "WAITING_ENGINEER",
    "WAITING_EXPERT",
    "BLOCKED",
    "COMPLETED",
    "CANCELLED",
    "FAILED",
}
TERMINAL_WORKFLOW_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}


@dataclass(slots=True)
class WorkflowPolicyDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    required_action: str | None = None
    required_role: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "required_action": self.required_action,
            "required_role": self.required_role,
        }


class MaintenanceWorkflowPolicyService:
    WRITE_ROLES = {"engineer", "expert", "admin"}
    REVIEW_ROLES = {"engineer", "expert", "admin"}
    HIGH_RISK_REVIEW_ROLES = {"expert", "admin"}
    FORMAL_TASK_ROLES = {"engineer", "admin"}
    TASK_EXECUTION_ROLES = {"engineer", "expert", "admin"}

    STAGE_TRANSITIONS = {
        "CASE_ANALYSIS": {"EVIDENCE_REVIEW"},
        "EVIDENCE_REVIEW": {"DIAGNOSIS_REVIEW", "CASE_ANALYSIS"},
        "DIAGNOSIS_REVIEW": {"SOP_DRAFT", "CASE_ANALYSIS"},
        "SOP_DRAFT": {"SOP_REVIEW", "DIAGNOSIS_REVIEW"},
        "SOP_REVIEW": {"TASK_DRAFT", "SOP_DRAFT", "DIAGNOSIS_REVIEW"},
        "TASK_DRAFT": {"TASK_CREATED", "SOP_REVIEW"},
        "TASK_CREATED": {"TASK_EXECUTION"},
        "TASK_EXECUTION": {"RESULT_VERIFICATION"},
        "RESULT_VERIFICATION": {"TASK_COMPLETED", "TASK_EXECUTION"},
        "TASK_COMPLETED": {"CORRECTION_REVIEW", "CLOSED"},
        "CORRECTION_REVIEW": {"CLOSED"},
        "CLOSED": set(),
    }

    STEP_TRANSITIONS = {
        "PENDING": {"IN_PROGRESS", "SKIPPED_WITH_REASON", "BLOCKED"},
        "IN_PROGRESS": {"COMPLETED", "BLOCKED", "FAILED"},
        "BLOCKED": {"IN_PROGRESS", "FAILED"},
        "FAILED": {"IN_PROGRESS"},
        "COMPLETED": set(),
        "SKIPPED_WITH_REASON": set(),
    }

    @classmethod
    def can_transition_stage(cls, current: str, target: str) -> WorkflowPolicyDecision:
        if target == current:
            return WorkflowPolicyDecision(True)
        if target not in cls.STAGE_TRANSITIONS.get(current, set()):
            return WorkflowPolicyDecision(
                False,
                [f"illegal workflow stage transition: {current} -> {target}"],
            )
        return WorkflowPolicyDecision(True)

    @staticmethod
    def can_create_diagnosis(
        *,
        case_status: str,
        has_input_evidence: bool,
        evidence_has_locator: bool,
        citation_count: int,
        open_high_conflicts: int,
        hypothesis_count: int,
    ) -> WorkflowPolicyDecision:
        reasons: list[str] = []
        if case_status not in {"EVIDENCE_READY", "MULTIPLE_POSSIBILITIES", "DIAGNOSIS_READY"}:
            reasons.append("case is not evidence ready")
        if not has_input_evidence:
            reasons.append("user text or media evidence is required")
        if not evidence_has_locator:
            reasons.append("evidence source locator is required")
        if citation_count <= 0:
            reasons.append("validated official knowledge citation is required")
        if open_high_conflicts:
            reasons.append("unresolved high-risk evidence conflict exists")
        if hypothesis_count <= 0:
            reasons.append("diagnostic hypothesis is required")
        return WorkflowPolicyDecision(
            not reasons,
            reasons,
            required_action="resolve evidence or retrieve official knowledge" if reasons else None,
            required_role="engineer",
        )

    @staticmethod
    def can_confirm_diagnosis(*, action: str, actor_role: str, high_risk: bool) -> WorkflowPolicyDecision:
        if action == "USER_CONFIRM":
            allowed = actor_role in {"engineer", "expert", "admin"}
            return WorkflowPolicyDecision(allowed, [] if allowed else ["viewer cannot confirm diagnosis"])
        if action == "ENGINEER_CONFIRM":
            allowed = actor_role in {"engineer", "admin"}
            return WorkflowPolicyDecision(allowed, [] if allowed else ["engineer confirmation role required"])
        if action == "EXPERT_REVIEW":
            allowed = actor_role in {"expert", "admin"}
            return WorkflowPolicyDecision(allowed, [] if allowed else ["expert review role required"])
        if action in {"REJECT", "REQUEST_REANALYSIS"}:
            allowed = actor_role in {"engineer", "expert", "admin"}
            return WorkflowPolicyDecision(allowed, [] if allowed else ["write role required"])
        return WorkflowPolicyDecision(False, ["unsupported diagnosis confirmation action"])

    @staticmethod
    def can_create_sop(
        *,
        diagnosis_status: str,
        citation_count: int,
        safety_count: int,
        device_model_confirmed: bool,
        open_high_conflicts: int,
        high_risk: bool,
        expert_reviewed: bool,
    ) -> WorkflowPolicyDecision:
        reasons: list[str] = []
        if diagnosis_status not in {"EVIDENCE_SUPPORTED", "USER_CONFIRMED", "ENGINEER_CONFIRMED"}:
            reasons.append("diagnosis must be evidence supported or human confirmed")
        if citation_count <= 0:
            reasons.append("valid citations are required")
        if safety_count <= 0:
            reasons.append("safety requirements are required")
        if not device_model_confirmed:
            reasons.append("device model must be resolved or human confirmed")
        if open_high_conflicts:
            reasons.append("unresolved high-risk evidence conflict exists")
        if high_risk and not expert_reviewed:
            reasons.append("high-risk diagnosis requires expert review")
        return WorkflowPolicyDecision(
            not reasons,
            reasons,
            required_action="complete diagnosis and safety review" if reasons else None,
            required_role="expert" if high_risk and not expert_reviewed else "engineer",
        )

    @classmethod
    def can_review_sop(cls, *, actor_role: str, high_risk: bool) -> WorkflowPolicyDecision:
        roles = cls.HIGH_RISK_REVIEW_ROLES if high_risk else cls.REVIEW_ROLES
        allowed = actor_role in roles
        return WorkflowPolicyDecision(
            allowed,
            [] if allowed else ["high-risk SOP requires expert or admin review" if high_risk else "SOP review role required"],
            required_role="expert" if high_risk else "engineer",
        )

    @staticmethod
    def can_create_task_draft(*, approved_sop: bool, personal_preparation_confirmed: bool) -> WorkflowPolicyDecision:
        allowed = approved_sop or personal_preparation_confirmed
        return WorkflowPolicyDecision(
            allowed,
            [] if allowed else ["approved SOP or explicit personal preparation confirmation is required"],
            required_action=None if allowed else "approve SOP or confirm draft-only preparation",
        )

    @classmethod
    def can_create_formal_task(
        cls,
        *,
        actor_role: str,
        task_draft_valid: bool,
        sop_approved: bool,
        device_exists: bool,
        safety_present: bool,
        verification_present: bool,
        citations_present: bool,
        assignee_valid: bool,
    ) -> WorkflowPolicyDecision:
        reasons: list[str] = []
        if actor_role not in cls.FORMAL_TASK_ROLES:
            reasons.append("only engineer or admin can create a formal task")
        if not task_draft_valid:
            reasons.append("valid task draft is required")
        if not sop_approved:
            reasons.append("approved SOP is required")
        if not device_exists:
            reasons.append("existing device is required")
        if not safety_present:
            reasons.append("safety requirements are required")
        if not verification_present:
            reasons.append("verification requirements are required")
        if not citations_present:
            reasons.append("citations are required")
        if not assignee_valid:
            reasons.append("assignee must have an executable role")
        return WorkflowPolicyDecision(not reasons, reasons, required_role="engineer")

    @classmethod
    def can_transition_step(
        cls,
        *,
        current: str,
        target: str,
        is_safety_step: bool,
        skip_reason: str | None,
        prerequisites_satisfied: bool,
    ) -> WorkflowPolicyDecision:
        reasons: list[str] = []
        if target not in cls.STEP_TRANSITIONS.get(current, set()):
            reasons.append(f"illegal task step transition: {current} -> {target}")
        if target == "SKIPPED_WITH_REASON" and not skip_reason:
            reasons.append("skipped step requires reason")
        if target == "SKIPPED_WITH_REASON" and is_safety_step:
            reasons.append("safety step cannot be skipped")
        if target in {"IN_PROGRESS", "COMPLETED"} and not prerequisites_satisfied:
            reasons.append("step prerequisites are not satisfied")
        return WorkflowPolicyDecision(not reasons, reasons)

    @staticmethod
    def can_verify_completion(
        *,
        required_steps_complete: bool,
        safety_steps_complete: bool,
        verification_steps_complete: bool,
        unresolved_safety_events: int,
        required_measurements_present: bool,
        required_media_present: bool,
    ) -> WorkflowPolicyDecision:
        reasons: list[str] = []
        if not required_steps_complete:
            reasons.append("required task steps are incomplete")
        if not safety_steps_complete:
            reasons.append("safety steps are incomplete")
        if not verification_steps_complete:
            reasons.append("verification steps are incomplete")
        if unresolved_safety_events:
            reasons.append("unresolved safety event exists")
        if not required_measurements_present:
            reasons.append("required measurements are missing")
        if not required_media_present:
            reasons.append("required execution media is missing")
        return WorkflowPolicyDecision(not reasons, reasons, required_action="complete verification evidence")

    @staticmethod
    def can_create_correction(*, task_completed: bool, evidence_count: int) -> WorkflowPolicyDecision:
        reasons: list[str] = []
        if not task_completed:
            reasons.append("completed task is required")
        if evidence_count <= 0:
            reasons.append("traceable workflow evidence is required")
        return WorkflowPolicyDecision(
            not reasons,
            reasons,
            required_action="attach execution evidence" if reasons else None,
            required_role="engineer",
        )
