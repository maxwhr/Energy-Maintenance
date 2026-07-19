from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


CaseStatus = Literal[
    "DRAFT", "MEDIA_UPLOADED", "ANALYZING", "NEEDS_CLARIFICATION", "EVIDENCE_READY",
    "DIAGNOSIS_READY", "MULTIPLE_POSSIBILITIES", "INSUFFICIENT_EVIDENCE", "SOP_DRAFT_READY",
    "TASK_DRAFT_READY", "ARCHIVED", "FAILED",
]
EvidenceModality = Literal["USER_TEXT", "IMAGE", "OCR_TEXT", "VISUAL_REGION", "FILE_METADATA", "KNOWLEDGE_TEXT"]
ObservationStatus = Literal["OBSERVED", "INFERRED", "USER_CONFIRMED", "LOW_CONFIDENCE", "CONTRADICTED", "REJECTED"]


class MultimodalCaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    user_query: str | None = Field(default=None, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=128)
    device_id: UUID | None = None
    device_model: str | None = Field(default=None, max_length=128)
    product_family: str | None = Field(default=None, max_length=128)
    equipment_category: str | None = Field(default=None, max_length=64)
    reported_symptoms: list[str] = Field(default_factory=list, max_length=30)
    occurrence_conditions: list[str] = Field(default_factory=list, max_length=30)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)


class MultimodalCaseClarify(BaseModel):
    answers: dict[str, str] = Field(min_length=1, max_length=30)
    confirmed_facts: dict[str, Any] = Field(default_factory=dict)


class MultimodalAnalyzeRequest(BaseModel):
    dry_run: bool = True
    mock_run: bool = False
    allow_real_api: bool = False
    force: bool = False


class MultimodalRetrieveRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=10)
    requested_information: list[str] = Field(default_factory=list, max_length=10)
    persist_result: bool = False
    request_id: str | None = Field(default=None, min_length=8, max_length=128)


class MultimodalDiagnoseRequest(BaseModel):
    proposed_actions: list[str] = Field(default_factory=list, max_length=20)


class MultimodalSopDraftRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class MultimodalTaskDraftRequest(BaseModel):
    sop_user_confirmed: bool = False
    assigned_role: str = Field(default="engineer", max_length=64)


class EvidenceDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    confirmed_value: str | None = Field(default=None, max_length=500)


class MultimodalEvidenceCreate(BaseModel):
    media_id: UUID | None = None
    ocr_result_id: UUID | None = None
    analysis_id: UUID | None = None
    frame_id: str | None = Field(default=None, max_length=128)
    region_id: str | None = Field(default=None, max_length=128)
    modality: EvidenceModality
    evidence_type: Literal[
        "NAMEPLATE", "DEVICE_MODEL", "ALARM_CODE", "ALARM_NAME", "INDICATOR_LIGHT", "SCREEN_TEXT",
        "COMPONENT", "PHYSICAL_DAMAGE", "CONNECTION_STATE", "COMMUNICATION_STATE", "OPERATING_STATE",
        "SAFETY_HAZARD", "GENERAL_OBSERVATION",
    ]
    source_type: Literal[
        "USER_INPUT", "OCR_PROVIDER", "MULTIMODAL_PROVIDER", "DETERMINISTIC_PARSER", "FILE_METADATA",
        "OFFICIAL_KNOWLEDGE",
    ]
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_text: str | None = Field(default=None, max_length=4000)
    normalized_text: str | None = Field(default=None, max_length=4000)
    visual_attributes: dict[str, Any] = Field(default_factory=dict)
    bounding_box: dict[str, float] | list[float] | None = None
    page_or_frame_locator: dict[str, Any] = Field(default_factory=dict)
    device_model_candidates: list[str] = Field(default_factory=list, max_length=20)
    alarm_code_candidates: list[str] = Field(default_factory=list, max_length=20)
    component_candidates: list[str] = Field(default_factory=list, max_length=30)
    indicator_state_candidates: list[str] = Field(default_factory=list, max_length=20)
    symptom_candidates: list[str] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    observation_status: ObservationStatus
    provider: str | None = Field(default=None, max_length=64)
    provider_model: str | None = Field(default=None, max_length=128)
    provider_trace_id: str | None = Field(default=None, max_length=128)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observation_status")
    @classmethod
    def enforce_inference_boundary(cls, value: str, info):
        source_type = info.data.get("source_type")
        if source_type == "MULTIMODAL_PROVIDER" and value in {"OBSERVED", "USER_CONFIRMED"}:
            raise ValueError("multimodal provider output must remain INFERRED or LOW_CONFIDENCE until confirmed")
        if source_type == "OCR_PROVIDER" and value == "USER_CONFIRMED":
            raise ValueError("OCR output cannot be user-confirmed at creation time")
        return value


class MultimodalEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: str
    case_id: str
    media_id: UUID | None = None
    ocr_result_id: UUID | None = None
    analysis_id: UUID | None = None
    frame_id: str | None = None
    region_id: str | None = None
    modality: str
    evidence_type: str
    source_type: str
    source_hash: str
    observed_text: str | None = None
    normalized_text: str | None = None
    visual_attributes: dict[str, Any] = Field(default_factory=dict)
    bounding_box: dict[str, float] | list[float] | None = None
    page_or_frame_locator: dict[str, Any] = Field(default_factory=dict)
    device_model_candidates: list[str] = Field(default_factory=list)
    alarm_code_candidates: list[str] = Field(default_factory=list)
    component_candidates: list[str] = Field(default_factory=list)
    indicator_state_candidates: list[str] = Field(default_factory=list)
    symptom_candidates: list[str] = Field(default_factory=list)
    confidence: float
    observation_status: str
    provider: str | None = None
    provider_model: str | None = None
    provider_trace_id: str | None = None
    user_confirmed: bool
    contradicted: bool
    contradiction_reason: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class MultimodalConflictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conflict_id: str
    case_id: str
    conflict_type: str
    evidence_ids: list[str] = Field(default_factory=list)
    severity: str
    resolution_required: bool
    recommended_question: str | None = None
    resolved_by: UUID | None = None
    resolution_status: str
    resolution_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class DiagnosticHypothesisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hypothesis_id: str
    case_id: str
    fault_category: str
    fault_name: str
    applicable_device: str | None = None
    required_conditions: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    knowledge_citation_ids: list[str] = Field(default_factory=list)
    confidence: float
    confidence_level: str
    status: str
    recommended_checks: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MultimodalCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: str
    title: str
    status: str
    user_query: str | None = None
    normalized_query: str | None = None
    conversation_id: str | None = None
    device_id: UUID | None = None
    device_model: str | None = None
    product_family: str | None = None
    equipment_category: str | None = None
    alarm_codes: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    reported_symptoms: list[str] = Field(default_factory=list)
    occurrence_conditions: list[str] = Field(default_factory=list)
    user_confirmed_facts: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    clarifying_questions: list[dict[str, Any] | str] = Field(default_factory=list)
    media_ids: list[str] = Field(default_factory=list)
    knowledge_citations: list[dict[str, Any]] = Field(default_factory=list)
    safety_level: str
    confidence_status: str
    diagnosis_status: str
    sop_draft_id: UUID | None = None
    task_draft_id: UUID | None = None
    analysis_job_ids: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    last_error_code: str | None = None
    last_error_message: str | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0
    region_count: int = 0
    conflict_count: int = 0
    hypothesis_count: int = 0


class MultimodalCasePage(BaseModel):
    items: list[MultimodalCaseRead]
    total: int
    page: int
    page_size: int
