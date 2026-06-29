from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeviceMaintenanceRecordBase(BaseModel):
    device_id: UUID
    task_id: UUID | None = None
    diagnosis_trace_id: str | None = None
    qa_trace_id: str | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str | None = None
    root_cause: str | None = None
    repair_action: str | None = None
    replaced_parts: str | None = None
    verification_result: str | None = None
    is_recurrent: bool = False
    recurrent_reference_record_id: UUID | None = None
    completed_by: UUID | None = None
    completed_at: datetime | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata_json: dict[str, Any] | None = None


class DeviceMaintenanceRecordCreate(DeviceMaintenanceRecordBase):
    pass


class DeviceMaintenanceRecordUpdate(BaseModel):
    task_id: UUID | None = None
    diagnosis_trace_id: str | None = None
    qa_trace_id: str | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str | None = None
    root_cause: str | None = None
    repair_action: str | None = None
    replaced_parts: str | None = None
    verification_result: str | None = None
    is_recurrent: bool | None = None
    recurrent_reference_record_id: UUID | None = None
    completed_by: UUID | None = None
    completed_at: datetime | None = None
    attachments: list[dict[str, Any]] | None = None
    metadata_json: dict[str, Any] | None = None


class DeviceMaintenanceRecordRead(DeviceMaintenanceRecordBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
