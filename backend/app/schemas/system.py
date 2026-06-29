from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserBase(BaseModel):
    username: str
    display_name: str | None = None
    role: str = "viewer"
    status: str = "active"
    is_active: bool = True


class UserCreate(UserBase):
    password_hash: str | None = None


class UserUpdate(BaseModel):
    password_hash: str | None = None
    display_name: str | None = None
    role: str | None = None
    status: str | None = None
    is_active: bool | None = None
    last_login_at: datetime | None = None


class UserRead(UserBase):
    id: UUID
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceBase(BaseModel):
    device_code: str | None = None
    device_name: str
    manufacturer: str
    product_series: str | None = None
    model: str | None = None
    device_type: str = "pv_inverter"
    station_name: str | None = None
    location: str | None = None
    commissioning_date: datetime | None = None
    status: str = "normal"
    last_fault_at: datetime | None = None
    last_maintenance_at: datetime | None = None
    fault_count: int = 0
    maintenance_count: int = 0
    metadata_json: dict[str, Any] | None = None
    description: str | None = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    device_code: str | None = None
    device_name: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    model: str | None = None
    device_type: str | None = None
    station_name: str | None = None
    location: str | None = None
    commissioning_date: datetime | None = None
    status: str | None = None
    last_fault_at: datetime | None = None
    last_maintenance_at: datetime | None = None
    fault_count: int | None = None
    maintenance_count: int | None = None
    metadata_json: dict[str, Any] | None = None
    description: str | None = None


class DeviceRead(DeviceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemInfo(BaseModel):
    project: str
    scope: str
    manufacturers: list[str]
    device_type: str
    product_series: list[str]
    deployment_target: str
    formal_database: str


class SystemStatus(BaseModel):
    service_status: str
    database_status: str
    document_count: int
    chunk_count: int
    qa_record_count: int
    diagnosis_record_count: int
    maintenance_task_count: int
