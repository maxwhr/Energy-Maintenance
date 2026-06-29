from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.media import MediaContextItem


ALLOWED_SOP_MANUFACTURERS = {"huawei", "sungrow"}
ALLOWED_SOP_PRODUCT_SERIES = {"SUN2000", "FusionSolar", "SG", "other"}
ALLOWED_SOP_DEVICE_TYPES = {"pv_inverter"}
ALLOWED_SOP_FAULT_TYPES = {
    "low_insulation",
    "low_insulation_resistance",
    "overtemperature",
    "over_temperature",
    "fan_fault",
    "communication_fault",
    "communication_interruption",
    "device_offline",
    "mppt_low_power",
    "mppt_abnormal",
    "low_power_generation",
    "grid_fault",
    "grid_connection_fault",
    "ac_overvoltage",
    "ac_undervoltage",
    "dc_abnormal",
    "alarm_code_query",
    "unknown",
}
ALLOWED_SOP_MAINTENANCE_LEVELS = {"level_1", "level_2", "level_3"}
ALLOWED_SOP_TEMPLATE_STATUSES = {"draft", "active", "archived"}
ALLOWED_SOP_EXECUTION_STATUSES = {"not_started", "in_progress", "completed", "aborted"}


class SOPStep(BaseModel):
    step_index: int = Field(..., ge=1)
    step_title: str = Field(..., min_length=1, max_length=160)
    instruction: str = Field(..., min_length=1, max_length=2000)
    expected_result: str | None = Field(default=None, max_length=1000)
    safety_note: str | None = Field(default=None, max_length=1000)


class SOPChecklistResult(BaseModel):
    step_index: int = Field(..., ge=1)
    step_title: str
    checked: bool = False
    note: str | None = None
    checked_at: datetime | None = None


class SOPReference(BaseModel):
    document_id: UUID | str | None = None
    document_title: str | None = None
    chunk_id: UUID | str | None = None
    chunk_index: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    quote: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    document_type: str | None = None
    source: str | None = None
    score: float | None = None


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _coerce_version(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(float(stripped))
    except ValueError as exc:
        raise ValueError("version must be an integer-compatible value") from exc


class SOPTemplateBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    fault_type: str | None = None
    maintenance_level: str = "level_1"
    steps: list[dict[str, Any]] = Field(default_factory=list)
    safety_requirements: list[dict[str, Any]] = Field(default_factory=list)
    tools_required: list[dict[str, Any]] = Field(default_factory=list)
    materials_required: list[dict[str, Any]] = Field(default_factory=list)
    compliance_notes: str | None = None
    status: str = "draft"
    version: int = 1
    created_by: UUID | None = None
    updated_by: UUID | None = None
    metadata_json: dict[str, Any] | None = None

    @field_validator("title", "manufacturer", "product_series", "device_type", "fault_type", "maintenance_level", "status")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: int | str | None) -> int:
        normalized = _coerce_version(value)
        return 1 if normalized is None else normalized


class SOPTemplateCreate(SOPTemplateBase):
    pass


class SOPTemplateUpdate(BaseModel):
    title: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    fault_type: str | None = None
    maintenance_level: str | None = None
    steps: list[dict[str, Any]] | None = None
    safety_requirements: list[dict[str, Any]] | None = None
    tools_required: list[dict[str, Any]] | None = None
    materials_required: list[dict[str, Any]] | None = None
    compliance_notes: str | None = None
    status: str | None = None
    version: int | str | None = None
    updated_by: UUID | None = None
    metadata_json: dict[str, Any] | None = None

    @field_validator("title", "manufacturer", "product_series", "device_type", "fault_type", "maintenance_level", "status")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, value: int | str | None) -> int | None:
        return _coerce_version(value)


class SOPTemplateRead(SOPTemplateBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SOPExecutionRecordBase(BaseModel):
    task_id: UUID | None = None
    template_id: UUID
    executor_id: UUID | None = None
    step_results: list[dict[str, Any]] = Field(default_factory=list)
    abnormal_notes: str | None = None
    status: str = "not_started"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None

    @field_validator("status")
    @classmethod
    def strip_status(cls, value: str | None) -> str | None:
        return _clean_text(value)


class SOPExecutionRecordCreate(SOPExecutionRecordBase):
    pass


class SOPExecutionRecordUpdate(BaseModel):
    step_results: list[dict[str, Any]] | None = None
    abnormal_notes: str | None = None
    status: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None

    @field_validator("status")
    @classmethod
    def strip_status(cls, value: str | None) -> str | None:
        return _clean_text(value)


class SOPExecutionRecordRead(SOPExecutionRecordBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SOPTemplatePage(BaseModel):
    items: list[SOPTemplateRead]
    total: int
    page: int
    page_size: int


class SOPGenerateRequest(BaseModel):
    device_id: UUID | None = None
    diagnosis_trace_id: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = None
    product_series: str | None = None
    model: str | None = Field(default=None, max_length=128)
    device_type: str = "pv_inverter"
    fault_type: str = "unknown"
    alarm_code: str | None = Field(default=None, max_length=64)
    maintenance_level: str = "level_2"
    include_references: bool = True
    enable_kg_enhancement: bool = True
    enable_model_enhancement: bool = False
    model_provider: str = "rule_based"
    allow_model_fallback: bool = True

    @field_validator(
        "diagnosis_trace_id",
        "manufacturer",
        "product_series",
        "model",
        "device_type",
        "fault_type",
        "alarm_code",
        "maintenance_level",
        "model_provider",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


class SOPGenerateResponse(BaseModel):
    source: Literal["template", "rule_based"]
    template_id: UUID | None = None
    title: str
    manufacturer: str | None = None
    product_series: str | None = None
    model: str | None = None
    device_type: str = "pv_inverter"
    fault_type: str = "unknown"
    alarm_code: str | None = None
    maintenance_level: str = "level_2"
    steps: list[dict[str, Any]] = Field(default_factory=list)
    safety_requirements: list[dict[str, Any]] = Field(default_factory=list)
    tools_required: list[dict[str, Any]] = Field(default_factory=list)
    materials_required: list[dict[str, Any]] = Field(default_factory=list)
    compliance_notes: str | None = None
    references: list[dict[str, Any]] = Field(default_factory=list)
    media_items: list[MediaContextItem] = Field(default_factory=list)
    media_notice: str | None = None
    kg_context: dict[str, Any] = Field(default_factory=dict)
    kg_tools: list[dict[str, Any]] = Field(default_factory=list)
    kg_parts: list[dict[str, Any]] = Field(default_factory=list)
    kg_safety_risks: list[dict[str, Any]] = Field(default_factory=list)
    kg_steps: list[dict[str, Any]] = Field(default_factory=list)
    kg_evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.4
    model_provider: str = "rule_based"
    model_name: str = "sop_rule_engine_v1"
    model_enhanced: bool = False
    fallback_used: bool = False
    model_call_trace_id: str | None = None


class SOPExecutionRecordDetail(SOPExecutionRecordRead):
    template: SOPTemplateRead | None = None


class SOPExecutionPage(BaseModel):
    items: list[SOPExecutionRecordRead]
    total: int
    page: int
    page_size: int
