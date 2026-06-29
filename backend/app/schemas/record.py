from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QARecordRead(BaseModel):
    id: UUID
    question: str
    normalized_query: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_id: UUID | None = None
    device_type: str = "pv_inverter"
    document_type: str | None = None
    answer: str
    references: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    suggested_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    related_history: list[dict[str, Any]] = Field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None
    confidence: float | None = None
    trace_id: str
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiagnosisRecordRead(BaseModel):
    id: UUID
    manufacturer: str | None = None
    product_series: str | None = None
    device_id: UUID | None = None
    device_type: str = "pv_inverter"
    device_name: str | None = None
    model: str | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    alarm_info: str | None = None
    fault_description: str
    device_status: str | None = None
    possible_causes: list[str] = Field(default_factory=list)
    inspection_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    references: list[dict[str, Any]] = Field(default_factory=list)
    related_history: list[dict[str, Any]] = Field(default_factory=list)
    media_ids: list[UUID] | list[str] = Field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None
    confidence: float | None = None
    trace_id: str
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelCallLogBase(BaseModel):
    trace_id: str | None = None
    module: str | None = None
    provider: str | None = None
    model_name: str | None = None
    call_type: str = "other"
    prompt: str | None = None
    response: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    latency_ms: int | None = None
    success: bool = True
    error_message: str | None = None
    created_by: UUID | None = None


class ModelCallLogCreate(ModelCallLogBase):
    pass


class ModelCallLogUpdate(BaseModel):
    response: str | None = None
    response_payload: dict[str, Any] | None = None
    latency_ms: int | None = None
    success: bool | None = None
    error_message: str | None = None


class ModelCallLogRead(ModelCallLogBase):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
