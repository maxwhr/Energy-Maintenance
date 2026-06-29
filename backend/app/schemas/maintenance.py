from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaintenanceTaskCreate(BaseModel):
    title: str
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    device_id: UUID | None = None
    device_name: str | None = None
    model: str | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str | None = None
    priority: str = "medium"
    task_status: str = "pending"
    assignee: str | None = None
    status: str = "pending"
    assignee_id: UUID | None = None
    due_date: datetime | None = None
    source_type: str = "manual"
    source_trace_id: str | None = None
    sop_template_id: UUID | None = None
    sop_execution_id: UUID | None = None
    suggested_steps: list[dict[str, Any]] | list[str] = Field(default_factory=list)
    root_cause: str | None = None
    repair_action: str | None = None
    replaced_parts: list[dict[str, Any]] | list[str] = Field(default_factory=list)
    verification_result: str | None = None
    is_recurrent: bool = False
    completed_by: UUID | None = None
    created_by: UUID | None = None


class MaintenanceTaskRead(MaintenanceTaskCreate):
    id: UUID
    result_summary: str | None = None
    completion_notes: str | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaintenanceTaskStatusUpdate(BaseModel):
    task_status: str
    status: str | None = None
    result_summary: str | None = None
    completion_notes: str | None = None
    metadata_json: dict[str, Any] | None = None
