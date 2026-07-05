from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


MediaJobType = Literal["ocr", "multimodal_analysis", "combined", "manual_review"]
MediaJobStatus = Literal["pending", "running", "succeeded", "failed", "blocked", "cancelled"]
MediaAnalysisReviewStatus = Literal["pending", "accepted", "rejected", "revised"]


class MediaProcessingJobCreate(BaseModel):
    job_type: MediaJobType
    provider_code: str | None = Field(default=None, max_length=64)
    capability: str | None = Field(default=None, max_length=64)
    analysis_type: str | None = Field(default=None, max_length=64)
    dry_run: bool = True
    mock_run: bool = False
    real_run: bool = False
    agent_run_id: str | None = Field(default=None, max_length=128)
    input_summary: dict[str, Any] = Field(default_factory=dict)


class MediaProcessingJobRead(BaseModel):
    id: UUID
    media_id: UUID
    job_type: str
    provider_code: str
    provider_name: str | None = None
    model_name: str | None = None
    status: str
    input_hash: str | None = None
    progress: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_summary_json: dict[str, Any] | None = None
    result_summary_json: dict[str, Any] | None = None
    external_trace_id: str | None = None
    agent_run_id: str | None = None
    agent_tool_call_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MediaOCRResultRead(BaseModel):
    id: UUID
    media_id: UUID
    job_id: UUID | None = None
    provider_code: str
    provider_name: str | None = None
    model_name: str | None = None
    language: str | None = None
    text: str | None = None
    confidence: Decimal | float | None = None
    regions_json: list[Any] | dict[str, Any] | None = None
    raw_result_json: dict[str, Any] | None = None
    status: str | None = None
    external_trace_id: str | None = None
    created_by: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaAIAnalysisCreate(BaseModel):
    media_id: UUID
    job_id: UUID | None = None
    provider_code: str = "manual"
    provider_name: str | None = "Manual review"
    model_name: str | None = None
    analysis_type: str = "general"
    summary: str = Field(..., min_length=1, max_length=4000)
    detected_text: str | None = Field(default=None, max_length=4000)
    detected_alarm_codes_json: list[str] = Field(default_factory=list)
    detected_device_info_json: dict[str, Any] = Field(default_factory=dict)
    visual_findings_json: list[dict[str, Any]] = Field(default_factory=list)
    possible_faults_json: list[dict[str, Any]] = Field(default_factory=list)
    safety_risks_json: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions_json: list[dict[str, Any]] = Field(default_factory=list)
    limitations_json: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=0.5, ge=0, le=0.99)
    raw_response_json: dict[str, Any] = Field(default_factory=dict)


class MediaAIAnalysisRead(BaseModel):
    id: UUID
    media_id: UUID
    job_id: UUID | None = None
    provider_code: str
    provider_name: str | None = None
    model_name: str | None = None
    analysis_type: str | None = None
    summary: str | None = None
    detected_text: str | None = None
    detected_alarm_codes_json: list[Any] | None = None
    detected_device_info_json: dict[str, Any] | None = None
    visual_findings_json: list[Any] | dict[str, Any] | None = None
    possible_faults_json: list[Any] | dict[str, Any] | None = None
    safety_risks_json: list[Any] | dict[str, Any] | None = None
    recommended_actions_json: list[Any] | dict[str, Any] | None = None
    limitations_json: list[Any] | dict[str, Any] | None = None
    confidence: Decimal | float | None = None
    raw_response_json: dict[str, Any] | None = None
    external_trace_id: str | None = None
    human_review_status: str
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_json_fields(cls, value: Any) -> Any:
        if not hasattr(value, "__dict__"):
            return value
        for field_name in (
            "detected_alarm_codes_json",
            "visual_findings_json",
            "possible_faults_json",
            "safety_risks_json",
            "recommended_actions_json",
            "limitations_json",
        ):
            raw_value = getattr(value, field_name, None)
            if raw_value is None or isinstance(raw_value, (list, dict)):
                continue
            setattr(value, field_name, [raw_value])
        raw_device_info = getattr(value, "detected_device_info_json", None)
        if raw_device_info is not None and not isinstance(raw_device_info, dict):
            setattr(value, "detected_device_info_json", {"value": str(raw_device_info)})
        return value


class MediaAIAnalysisReview(BaseModel):
    review_status: MediaAnalysisReviewStatus = Field(alias="human_review_status")
    review_comment: str | None = Field(default=None, max_length=2000)

    model_config = {"populate_by_name": True}

    @field_validator("review_comment")
    @classmethod
    def strip_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class MediaEvidenceLinkCreate(BaseModel):
    media_id: UUID
    ocr_result_id: UUID | None = None
    analysis_id: UUID | None = None
    source_type: str = Field(..., min_length=1, max_length=64)
    source_id: str = Field(..., min_length=1, max_length=128)
    relation_type: str = Field(..., min_length=1, max_length=64)


class MediaEvidenceLinkRead(BaseModel):
    id: UUID
    media_id: UUID
    ocr_result_id: UUID | None = None
    analysis_id: UUID | None = None
    source_type: str
    source_id: str
    relation_type: str
    created_at: datetime
    created_by: UUID | None = None

    model_config = {"from_attributes": True}


class MediaMultimodalSummary(BaseModel):
    media_id: UUID
    jobs: list[MediaProcessingJobRead]
    ocr_results: list[MediaOCRResultRead]
    analyses: list[MediaAIAnalysisRead]
    evidence_links: list[MediaEvidenceLinkRead]
    provider_status: dict[str, Any]
    latest_ocr_status: str | None = None
    latest_analysis_status: str | None = None
    machine_result_boundary: str = "Machine OCR and multimodal analysis results are auxiliary evidence only."


class PageResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
