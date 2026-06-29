from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.media import MediaContextItem


ALLOWED_DIAGNOSIS_MANUFACTURERS = {"huawei", "sungrow"}
ALLOWED_DIAGNOSIS_PRODUCT_SERIES = {"SUN2000", "FusionSolar", "SG", "other"}
ALLOWED_DIAGNOSIS_DEVICE_TYPES = {"pv_inverter"}
ALLOWED_DIAGNOSIS_FAULT_TYPES = {
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


class DiagnosisAnalyzeRequest(BaseModel):
    device_id: UUID | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    model: str | None = Field(default=None, max_length=128)
    device_type: str = "pv_inverter"
    fault_type: str = "unknown"
    alarm_code: str | None = Field(default=None, max_length=64)
    fault_description: str = Field(..., min_length=1, max_length=4000)
    observed_symptoms: list[str] = Field(default_factory=list)
    media_ids: list[UUID] = Field(default_factory=list)
    use_ocr_text: bool = False
    include_history: bool = True
    enable_kg_enhancement: bool = True
    enable_model_enhancement: bool = False
    model_provider: str = "rule_based"
    allow_model_fallback: bool = True

    @field_validator(
        "manufacturer",
        "product_series",
        "model",
        "device_type",
        "fault_type",
        "alarm_code",
        "fault_description",
        "model_provider",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("observed_symptoms")
    @classmethod
    def clean_observed_symptoms(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            stripped = value.strip()
            if stripped:
                cleaned.append(stripped[:500])
        return cleaned[:20]


class DiagnosisReference(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    quote: str
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    document_type: str | None = None
    source: str | None = None
    score: float


class DiagnosisRelatedHistory(BaseModel):
    record_id: UUID
    device_id: UUID
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str | None = None
    root_cause: str | None = None
    repair_action: str | None = None
    verification_result: str | None = None
    is_recurrent: bool
    completed_at: datetime | None = None


class DiagnosisAnalyzeResponse(BaseModel):
    trace_id: str
    device_id: UUID | None = None
    fault_type: str
    alarm_code: str | None = None
    diagnosis_summary: str
    possible_causes: list[str] = Field(default_factory=list)
    inspection_steps: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    references: list[DiagnosisReference] = Field(default_factory=list)
    related_history: list[DiagnosisRelatedHistory] = Field(default_factory=list)
    media_ids: list[UUID] = Field(default_factory=list)
    media_items: list[MediaContextItem] = Field(default_factory=list)
    media_notice: str | None = None
    ocr_context: list[dict[str, Any]] = Field(default_factory=list)
    kg_context: dict[str, Any] = Field(default_factory=dict)
    kg_related_causes: list[dict[str, Any]] = Field(default_factory=list)
    kg_inspection_items: list[dict[str, Any]] = Field(default_factory=list)
    kg_recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    kg_safety_risks: list[dict[str, Any]] = Field(default_factory=list)
    kg_evidence: list[dict[str, Any]] = Field(default_factory=list)
    is_recurrent: bool = False
    recurrent_reference_record_id: UUID | None = None
    confidence: float = 0.2
    model_provider: str = "rule_based"
    model_name: str = "diagnosis_rule_engine_v1"
    model_enhanced: bool = False
    fallback_used: bool = False
    model_call_trace_id: str | None = None


class DiagnosisRecordItem(BaseModel):
    id: UUID
    trace_id: str
    device_id: UUID | None = None
    device_name: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    model: str | None = None
    device_type: str = "pv_inverter"
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str
    diagnosis_summary: str
    possible_causes: list[str] = Field(default_factory=list)
    inspection_steps: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    related_history: list[dict[str, Any]] = Field(default_factory=list)
    media_ids: list[str] = Field(default_factory=list)
    media_items: list[MediaContextItem] = Field(default_factory=list)
    media_notice: str | None = None
    ocr_context: list[dict[str, Any]] = Field(default_factory=list)
    kg_context: dict[str, Any] = Field(default_factory=dict)
    kg_related_causes: list[dict[str, Any]] = Field(default_factory=list)
    kg_inspection_items: list[dict[str, Any]] = Field(default_factory=list)
    kg_recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    kg_safety_risks: list[dict[str, Any]] = Field(default_factory=list)
    kg_evidence: list[dict[str, Any]] = Field(default_factory=list)
    is_recurrent: bool = False
    recurrent_reference_record_id: str | None = None
    confidence: float | None = None
    model_provider: str | None = None
    model_name: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosisRecordPage(BaseModel):
    items: list[DiagnosisRecordItem]
    total: int
    page: int
    page_size: int
