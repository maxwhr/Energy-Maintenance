from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QARecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "qa_records"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    document_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    retrieved_chunks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    suggested_steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    safety_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_qa_records_manufacturer", "manufacturer"),
        Index("ix_qa_records_product_series", "product_series"),
        Index("ix_qa_records_device_id", "device_id"),
        Index("ix_qa_records_device_type", "device_type"),
        Index("ix_qa_records_document_type", "document_type"),
        Index("ix_qa_records_model_provider", "model_provider"),
        Index("ix_qa_records_created_at", "created_at"),
    )


class DiagnosisRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "diagnosis_records"

    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fault_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alarm_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alarm_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    fault_description: Mapped[str] = mapped_column(Text, nullable=False)
    device_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    possible_causes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    inspection_steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    safety_notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recommended_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    media_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_diagnosis_records_manufacturer", "manufacturer"),
        Index("ix_diagnosis_records_product_series", "product_series"),
        Index("ix_diagnosis_records_device_id", "device_id"),
        Index("ix_diagnosis_records_device_type", "device_type"),
        Index("ix_diagnosis_records_fault_type", "fault_type"),
        Index("ix_diagnosis_records_alarm_code", "alarm_code"),
        Index("ix_diagnosis_records_model_provider", "model_provider"),
        Index("ix_diagnosis_records_created_at", "created_at"),
    )


class OperationLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "operation_logs"

    module: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_operation_logs_module", "module"),
        Index("ix_operation_logs_action", "action"),
        Index("ix_operation_logs_trace_id", "trace_id"),
        Index("ix_operation_logs_created_at", "created_at"),
    )


class ModelCallLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "model_call_logs"

    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    module: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    call_type: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_model_call_logs_trace_id", "trace_id"),
        Index("ix_model_call_logs_module", "module"),
        Index("ix_model_call_logs_provider", "provider"),
        Index("ix_model_call_logs_model_name", "model_name"),
        Index("ix_model_call_logs_call_type", "call_type"),
        Index("ix_model_call_logs_success", "success"),
        Index("ix_model_call_logs_created_at", "created_at"),
    )
