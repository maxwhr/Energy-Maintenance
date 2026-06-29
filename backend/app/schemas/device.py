from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PageResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class DeviceBase(BaseModel):
    device_code: str | None = Field(default=None, max_length=64)
    device_name: str = Field(min_length=1, max_length=128)
    manufacturer: str
    product_series: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=128)
    device_type: str = "pv_inverter"
    station_name: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    commissioning_date: datetime | None = None
    status: str = "normal"
    metadata_json: dict[str, Any] | None = None
    description: str | None = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    device_name: str | None = Field(default=None, min_length=1, max_length=128)
    manufacturer: str | None = None
    product_series: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=128)
    device_type: str | None = None
    station_name: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    commissioning_date: datetime | None = None
    status: str | None = None
    metadata_json: dict[str, Any] | None = None
    description: str | None = None


class DeviceRead(DeviceBase):
    id: UUID
    last_fault_at: datetime | None = None
    last_maintenance_at: datetime | None = None
    fault_count: int
    maintenance_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceMaintenanceRecordCreate(BaseModel):
    task_id: UUID | None = None
    diagnosis_trace_id: str | None = Field(default=None, max_length=64)
    qa_trace_id: str | None = Field(default=None, max_length=64)
    fault_type: str | None = Field(default=None, max_length=64)
    alarm_code: str | None = Field(default=None, max_length=64)
    fault_description: str | None = None
    root_cause: str | None = None
    repair_action: str | None = None
    replaced_parts: str | None = None
    verification_result: str | None = None
    is_recurrent: bool = False
    recurrent_reference_record_id: UUID | None = None
    completed_at: datetime | None = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    metadata_json: dict[str, Any] | None = None


class DeviceMaintenanceRecordRead(DeviceMaintenanceRecordCreate):
    id: UUID
    device_id: UUID
    completed_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceStatisticsSummary(BaseModel):
    total_devices: int
    normal_devices: int
    fault_devices: int
    maintenance_devices: int
    offline_devices: int
    retired_devices: int
    huawei_devices: int
    sungrow_devices: int
    recent_maintenance_records: int
