from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UploadedMediaBase(BaseModel):
    file_name: str
    original_file_name: str | None = None
    file_path: str
    file_ext: str | None = None
    mime_type: str | None = None
    file_size: int | None = None
    media_type: str = "other"
    description: str | None = None
    ocr_text: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    device_id: UUID | None = None
    task_id: UUID | None = None
    diagnosis_record_id: UUID | None = None
    qa_trace_id: str | None = None
    uploaded_by: UUID | None = None
    status: str = "uploaded"
    metadata_json: dict[str, Any] | None = None


class UploadedMediaCreate(UploadedMediaBase):
    pass


class UploadedMediaUpdate(BaseModel):
    description: str | None = None
    ocr_text: str | None = None
    media_type: str | None = None
    status: str | None = None
    metadata_json: dict[str, Any] | None = None


class UploadedMediaRead(UploadedMediaBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UploadedMediaListResponse(BaseModel):
    items: list[UploadedMediaRead]
    total: int
    page: int
    page_size: int


class MediaUploadResponse(BaseModel):
    media_id: UUID
    media_type: str
    description: str | None = None
    ocr_text: str = ""
    status: str
    file_name: str
    original_file_name: str | None = None
    ocr_status: str = "disabled"
    message: str = "OCR service is not configured"
    preview_url: str
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    device_id: UUID | None = None
    task_id: UUID | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    deduplicated: bool = False


class MediaContextItem(BaseModel):
    id: UUID
    file_name: str
    original_file_name: str | None = None
    media_type: str
    description: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    device_id: UUID | None = None
    device_name: str | None = None
    task_id: UUID | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    ocr_status: str = "disabled"
    ocr_message: str = "OCR service is not configured"
    ocr_error_summary: str | None = None
    ocr_provider: str | None = None
    ocr_lang: str | None = None
    ocr_processed_at: str | None = None
    ocr_text: str | None = None
    preview_url: str
    created_at: datetime | None = None


class OCRResult(BaseModel):
    status: str = "disabled"
    text: str = ""
    message: str = "OCR service is not configured"
    error_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OCRStatusResponse(BaseModel):
    enabled: bool
    provider: str
    status: str
    message: str
    lang: str
    command: str
    timeout_seconds: int
    max_image_mb: int
    available: bool = False
    error_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaOCRResponse(BaseModel):
    media_id: UUID
    status: str
    provider: str
    lang: str
    text: str = ""
    message: str
    error_summary: str | None = None
    processed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
