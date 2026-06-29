from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DeviceMaintenanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "device_maintenance_records"

    device_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id"), nullable=True)
    diagnosis_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qa_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fault_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alarm_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fault_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_parts: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurrent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    recurrent_reference_record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("device_maintenance_records.id"),
        nullable=True,
    )
    completed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    device: Mapped["Device"] = relationship(back_populates="maintenance_records")
    task: Mapped["MaintenanceTask | None"] = relationship(back_populates="maintenance_records")
    completed_by_user: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("ix_device_maintenance_records_device_id", "device_id"),
        Index("ix_device_maintenance_records_task_id", "task_id"),
        Index("ix_device_maintenance_records_fault_type", "fault_type"),
        Index("ix_device_maintenance_records_alarm_code", "alarm_code"),
        Index("ix_device_maintenance_records_completed_at", "completed_at"),
        Index("ix_device_maintenance_records_diagnosis_trace_id", "diagnosis_trace_id"),
        Index("ix_device_maintenance_records_qa_trace_id", "qa_trace_id"),
    )
