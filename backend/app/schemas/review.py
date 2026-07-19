from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeContributionBase(BaseModel):
    title: str
    content: str | None = None
    contribution_type: str = "maintenance_experience"
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    device_id: UUID | None = None
    source_type: str = "field_contribution"
    source_trace_id: str | None = None
    submitted_by: UUID | None = None
    review_status: str = "draft"
    review_comment: str | None = None
    approved_document_id: UUID | None = None
    metadata_json: dict[str, Any] | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    symptom_description: str | None = None
    diagnosis_process: str | None = None
    root_cause: str | None = None
    solution: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    parts_used: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    media_ids: list[UUID] = Field(default_factory=list)
    related_diagnosis_trace_id: str | None = None
    related_task_id: UUID | None = None
    qa_trace_id: str | None = None


class KnowledgeContributionCreate(KnowledgeContributionBase):
    pass


class KnowledgeContributionUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    contribution_type: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    device_id: UUID | None = None
    source_trace_id: str | None = None
    metadata_json: dict[str, Any] | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    symptom_description: str | None = None
    diagnosis_process: str | None = None
    root_cause: str | None = None
    solution: str | None = None
    tools_used: list[str] | None = None
    parts_used: list[str] | None = None
    safety_notes: list[str] | None = None
    media_ids: list[UUID] | None = None
    related_diagnosis_trace_id: str | None = None
    related_task_id: UUID | None = None
    qa_trace_id: str | None = None


class KnowledgeContributionRead(KnowledgeContributionBase):
    id: UUID
    content: str
    device_name: str | None = None
    submitted_by_name: str | None = None
    approved_document_title: str | None = None
    content_preview: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeContributionPage(BaseModel):
    items: list[KnowledgeContributionRead]
    total: int
    page: int
    page_size: int


class KnowledgeContributionActionRequest(BaseModel):
    comment: str | None = None


class KnowledgeContributionDetail(KnowledgeContributionRead):
    review_records: list[dict[str, Any]] = Field(default_factory=list)


class KnowledgeContributionConvertResponse(BaseModel):
    contribution: dict[str, Any]
    document: dict[str, Any]
    chunk_count: int


class KnowledgeReviewRecordBase(BaseModel):
    contribution_id: UUID | None = None
    document_id: UUID | None = None
    reviewer_id: UUID | None = None
    review_action: str
    review_comment: str | None = None
    before_status: str | None = None
    after_status: str | None = None
    reviewed_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None


class KnowledgeReviewRecordCreate(KnowledgeReviewRecordBase):
    pass


class KnowledgeReviewRecordRead(KnowledgeReviewRecordBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelOutputCorrectionBase(BaseModel):
    source_type: str = "qa"
    source_trace_id: str
    original_output: dict[str, Any]
    corrected_output: dict[str, Any]
    correction_reason: str | None = None
    submitted_by: UUID | None = None
    review_status: str = "pending_review"
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    converted_contribution_id: UUID | None = None
    metadata_json: dict[str, Any] | None = None


class ModelOutputCorrectionCreate(ModelOutputCorrectionBase):
    pass


class ModelOutputCorrectionUpdate(BaseModel):
    corrected_output: dict[str, Any] | None = None
    correction_reason: str | None = None
    review_status: str | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    converted_contribution_id: UUID | None = None
    metadata_json: dict[str, Any] | None = None


class ModelOutputCorrectionRead(ModelOutputCorrectionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeReviewActionRequest(BaseModel):
    comment: str | None = None


class VendorOfficialBatchApproveRequest(BaseModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    comment: str | None = Field(default=None, max_length=2000)


class VendorOfficialFlagRequest(BaseModel):
    action: Literal["needs_metadata", "marketing_only", "needs_ocr"]
    comment: str | None = Field(default=None, max_length=2000)


class VendorOfficialWithdrawRequest(BaseModel):
    target_status: Literal["pending_review", "needs_revision"] = "pending_review"
    reason: str = Field(min_length=10, max_length=2000)


class KnowledgeReviewDocumentItem(BaseModel):
    id: UUID
    title: str
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    document_type: str | None = None
    source: str | None = None
    parse_status: str | None = None
    review_status: str | None = None
    status: str | None = None
    chunk_count: int = 0
    page_count: int | None = None
    source_type: str | None = None
    metadata_json: dict[str, Any] | None = None
    reviewed_by: UUID | None = None
    reviewed_by_name: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    submitted_by: UUID | None = None
    submitted_by_name: str | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeReviewDocumentPage(BaseModel):
    items: list[KnowledgeReviewDocumentItem]
    total: int
    page: int
    page_size: int


class KnowledgeReviewDetail(BaseModel):
    document: KnowledgeReviewDocumentItem
    chunk_preview: list[dict[str, Any]]
    review_records: list[KnowledgeReviewRecordRead]
