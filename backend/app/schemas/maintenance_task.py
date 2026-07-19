from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.media import MediaContextItem


TASK_STATUSES = {"pending", "assigned", "in_progress", "paused", "completed", "cancelled"}
TASK_PRIORITIES = {"low", "medium", "high", "urgent"}


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class MaintenanceTaskCreateRequest(BaseModel):
    device_id: UUID | None = None
    diagnosis_trace_id: str | None = Field(default=None, max_length=64)
    qa_trace_id: str | None = Field(default=None, max_length=64)
    sop_template_id: UUID | None = None
    sop_execution_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    fault_type: str | None = Field(default=None, max_length=64)
    alarm_code: str | None = Field(default=None, max_length=64)
    fault_description: str | None = None
    priority: str = "medium"
    assignee_id: UUID | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    remark: str | None = None

    @field_validator("diagnosis_trace_id", "qa_trace_id", "title", "fault_type", "alarm_code", "fault_description", "priority", "remark")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


class MaintenanceTaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    priority: str | None = None
    fault_type: str | None = Field(default=None, max_length=64)
    alarm_code: str | None = Field(default=None, max_length=64)
    fault_description: str | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    remark: str | None = None
    sop_template_id: UUID | None = None
    sop_execution_id: UUID | None = None
    assignee_id: UUID | None = None

    @field_validator("title", "priority", "fault_type", "alarm_code", "fault_description", "remark")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


class MaintenanceTaskAssignRequest(BaseModel):
    assignee_id: UUID


class MaintenanceTaskCompleteRequest(BaseModel):
    root_cause: str = Field(min_length=1)
    repair_action: str = Field(min_length=1)
    replaced_parts: list[str] = Field(default_factory=list)
    verification_result: str = Field(min_length=1)
    is_recurrent: bool = False
    recurrent_reference_record_id: UUID | None = None
    completed_at: datetime | None = None
    maintenance_record_remark: str | None = None
    media_ids: list[UUID] = Field(default_factory=list)

    @field_validator("root_cause", "repair_action", "verification_result", "maintenance_record_remark")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("media_ids")
    @classmethod
    def validate_media_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) > 10:
            raise ValueError("media_ids supports at most 10 media items")
        return list(dict.fromkeys(values))


class MaintenanceTaskCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _clean_text(value) or ""


class MaintenanceTaskRead(BaseModel):
    id: UUID
    task_code: str
    title: str
    device_id: UUID | None = None
    device_name: str | None = None
    device_code: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    model: str | None = None
    device_type: str = "pv_inverter"
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str | None = None
    priority: str
    status: str
    task_status: str
    assignee_id: UUID | None = None
    assignee_name: str | None = None
    created_by: UUID | None = None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    sop_template_id: UUID | None = None
    sop_execution_id: UUID | None = None
    diagnosis_trace_id: str | None = None
    qa_trace_id: str | None = None
    source_type: str | None = None
    root_cause: str | None = None
    repair_action: str | None = None
    replaced_parts: list[str] = Field(default_factory=list)
    verification_result: str | None = None
    is_recurrent: bool = False
    completion_notes: str | None = None


class MaintenanceRecordFromTask(BaseModel):
    id: UUID
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
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceTaskDetail(BaseModel):
    task: MaintenanceTaskRead
    device: dict[str, Any] | None = None
    diagnosis_record: dict[str, Any] | None = None
    sop_template: dict[str, Any] | None = None
    sop_execution: dict[str, Any] | None = None
    maintenance_record: dict[str, Any] | None = None
    media_items: list[MediaContextItem] = Field(default_factory=list)
    media_notice: str | None = None
    allowed_transitions: list[str] = Field(default_factory=list)
    field_limitations: list[str] = Field(default_factory=list)


class MaintenanceTaskStatistics(BaseModel):
    total_tasks: int
    pending_tasks: int
    assigned_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    cancelled_tasks: int
    high_priority_tasks: int
    my_tasks: int


class MaintenanceTaskPage(BaseModel):
    items: list[MaintenanceTaskRead]
    total: int
    page: int
    page_size: int
