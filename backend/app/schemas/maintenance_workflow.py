from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


WorkflowStage = Literal[
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
WorkflowStatus = Literal[
    "ACTIVE",
    "WAITING_USER",
    "WAITING_ENGINEER",
    "WAITING_EXPERT",
    "BLOCKED",
    "COMPLETED",
    "CANCELLED",
    "FAILED",
]
DiagnosisStatus = Literal[
    "DRAFT",
    "NEEDS_CLARIFICATION",
    "MULTIPLE_POSSIBILITIES",
    "EVIDENCE_SUPPORTED",
    "USER_CONFIRMED",
    "ENGINEER_CONFIRMED",
    "REJECTED",
]
TaskRecordType = Literal[
    "START",
    "PAUSE",
    "RESUME",
    "STEP_RESULT",
    "MEASUREMENT",
    "PHOTO",
    "PART_REPLACEMENT",
    "SAFETY_EVENT",
    "NEW_FINDING",
    "VERIFICATION",
    "COMPLETION_REQUEST",
    "EXPERT_ASSISTANCE",
]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class IdempotentRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def clean_key(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("idempotency_key is required")
        return value


class MaintenanceWorkflowCreate(IdempotentRequest):
    case_id: str = Field(min_length=1, max_length=128)
    device_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("case_id", "reason")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean(value)


class DiagnosisDraftRequest(IdempotentRequest):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        return _clean(value)


class DiagnosisConfirmationRequest(IdempotentRequest):
    action: Literal[
        "USER_CONFIRM",
        "ENGINEER_CONFIRM",
        "EXPERT_REVIEW",
        "REJECT",
        "REQUEST_REANALYSIS",
    ]
    confirmed_fields: dict[str, Any] = Field(default_factory=dict)
    rejected_fields: list[str] = Field(default_factory=list)
    selected_hypothesis_id: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("selected_hypothesis_id", "comment")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean(value)

    @model_validator(mode="after")
    def validate_confirmation(self):
        if self.action in {"ENGINEER_CONFIRM", "EXPERT_REVIEW", "USER_CONFIRM"}:
            if not self.confirmed_fields and not self.selected_hypothesis_id:
                raise ValueError("confirmation requires confirmed_fields or selected_hypothesis_id")
        if self.action in {"REJECT", "REQUEST_REANALYSIS"} and not self.comment:
            raise ValueError("rejection or reanalysis requires comment")
        return self


class WorkflowSopDraftRequest(IdempotentRequest):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        return _clean(value)


class WorkflowSopReviewRequest(IdempotentRequest):
    action: Literal["APPROVE", "REJECT", "REQUEST_CHANGES", "CREATE_NEW_VERSION"]
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str) -> str:
        return _clean(value) or ""


class WorkflowTaskDraftRequest(IdempotentRequest):
    title: str | None = Field(default=None, max_length=255)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    assignee_role: Literal["engineer", "expert"] = "engineer"
    personal_preparation_confirmed: bool = False
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("title", "comment")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean(value)


class FormalTaskCreationRequest(IdempotentRequest):
    assignee_id: UUID | None = None
    comment: str = Field(min_length=1, max_length=1000)

    @field_validator("comment")
    @classmethod
    def clean_comment(cls, value: str) -> str:
        return _clean(value) or ""


class WorkflowTaskActionRequest(IdempotentRequest):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        return _clean(value)


class MeasurementValue(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: float | int | str
    unit: str = Field(min_length=1, max_length=32)
    within_expected_range: bool | None = None

    @field_validator("name", "unit")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return _clean(value) or ""


class WorkflowTaskRecordCreate(IdempotentRequest):
    record_type: TaskRecordType
    step_id: UUID | None = None
    content: str | None = Field(default=None, max_length=10000)
    media_ids: list[UUID] = Field(default_factory=list)
    measurements: list[MeasurementValue] = Field(default_factory=list)
    parts_replaced: list[str] = Field(default_factory=list)
    safety_state: Literal["NORMAL", "WARNING", "BLOCKED", "RESOLVED"] = "NORMAL"
    result: dict[str, Any] = Field(default_factory=dict)
    correction_of_id: UUID | None = None

    @field_validator("content")
    @classmethod
    def clean_content(cls, value: str | None) -> str | None:
        return _clean(value)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.record_type == "MEASUREMENT" and not self.measurements:
            raise ValueError("measurement record requires measurements with units")
        if self.record_type == "PHOTO" and not self.media_ids:
            raise ValueError("photo record requires media_ids")
        if self.record_type == "PART_REPLACEMENT" and not self.parts_replaced:
            raise ValueError("part replacement record requires parts_replaced")
        if self.record_type == "SAFETY_EVENT" and self.safety_state not in {"WARNING", "BLOCKED", "RESOLVED"}:
            raise ValueError("safety event requires WARNING, BLOCKED, or RESOLVED safety_state")
        if not (self.content or self.media_ids or self.measurements or self.parts_replaced or self.result):
            raise ValueError("execution record requires evidence content")
        return self


class WorkflowTaskStepUpdate(IdempotentRequest):
    status: Literal["IN_PROGRESS", "COMPLETED", "SKIPPED_WITH_REASON", "BLOCKED", "FAILED"]
    result_summary: str | None = Field(default=None, max_length=4000)
    evidence_ids: list[str] = Field(default_factory=list)
    skip_reason: str | None = Field(default=None, max_length=2000)
    verification_status: Literal["PENDING", "PASSED", "FAILED", "NOT_APPLICABLE"] = "PENDING"

    @field_validator("result_summary", "skip_reason")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean(value)

    @model_validator(mode="after")
    def validate_skip(self):
        if self.status == "SKIPPED_WITH_REASON" and not self.skip_reason:
            raise ValueError("skipped step requires skip_reason")
        return self


class WorkflowTaskVerificationRequest(IdempotentRequest):
    outcome: Literal["VERIFIED_SUCCESS", "VERIFIED_PARTIAL", "VERIFICATION_FAILED", "NEEDS_REWORK"]
    verification_summary: str = Field(min_length=1, max_length=4000)
    accepted_partial: bool = False
    required_measurements_present: bool = False
    required_media_present: bool = False

    @field_validator("verification_summary")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        return _clean(value) or ""

    @model_validator(mode="after")
    def validate_partial(self):
        if self.outcome == "VERIFIED_PARTIAL" and not self.accepted_partial:
            raise ValueError("partial result must be explicitly accepted")
        return self


class WorkflowTaskCompleteRequest(IdempotentRequest):
    comment: str = Field(min_length=1, max_length=2000)
    actual_fault_cause: str = Field(min_length=1, max_length=4000)
    actual_actions: list[str] = Field(min_length=1)
    replaced_parts: list[str] = Field(default_factory=list)
    final_device_status: str = Field(min_length=1, max_length=128)
    diagnosis_match_status: Literal["MATCHED", "PARTIALLY_MATCHED", "MISMATCHED", "UNDETERMINED"]
    user_feedback: str | None = Field(default=None, max_length=4000)

    @field_validator("comment", "actual_fault_cause", "final_device_status", "user_feedback")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean(value)


class WorkflowCorrectionCandidateRequest(IdempotentRequest):
    candidate_type: Literal[
        "ACTUAL_FAULT_MISMATCH",
        "SOP_INCOMPLETE",
        "MANUAL_AMBIGUITY",
        "MODEL_VARIANT",
        "ALARM_ALIAS",
        "ACTION_MISMATCH",
        "CITATION_LOCATOR_ERROR",
        "OCR_VISUAL_FEEDBACK",
    ]
    proposed_change: dict[str, Any]
    reason: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1)
    source_document_ids: list[UUID] = Field(default_factory=list)
    source_chunk_ids: list[UUID] = Field(default_factory=list)
    semantic_unit_ids: list[str] = Field(default_factory=list)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _clean(value) or ""


class WorkflowAdminActionRequest(IdempotentRequest):
    action: Literal["UNBLOCK", "CANCEL", "ARCHIVE"]
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _clean(value) or ""
