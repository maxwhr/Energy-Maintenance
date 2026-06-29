from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MaintenanceTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_tasks"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    device_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id"),
        nullable=True,
    )
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    fault_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alarm_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fault_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    task_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    assignee: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    assignee_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sop_template_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sop_templates.id"), nullable=True)
    sop_execution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sop_execution_records.id", use_alter=True, name="fk_maintenance_tasks_sop_execution_id"),
        nullable=True,
    )
    suggested_steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_parts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    verification_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_recurrent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped["Device | None"] = relationship(back_populates="maintenance_tasks")
    maintenance_records: Mapped[list["DeviceMaintenanceRecord"]] = relationship(back_populates="task")

    __table_args__ = (
        Index("ix_maintenance_tasks_manufacturer", "manufacturer"),
        Index("ix_maintenance_tasks_product_series", "product_series"),
        Index("ix_maintenance_tasks_device_type", "device_type"),
        Index("ix_maintenance_tasks_device_id", "device_id"),
        Index("ix_maintenance_tasks_fault_type", "fault_type"),
        Index("ix_maintenance_tasks_priority", "priority"),
        Index("ix_maintenance_tasks_status", "status"),
        Index("ix_maintenance_tasks_task_status", "task_status"),
        Index("ix_maintenance_tasks_source_trace_id", "source_trace_id"),
        Index("ix_maintenance_tasks_created_at", "created_at"),
    )
