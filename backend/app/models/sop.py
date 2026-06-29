from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SOPTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sop_templates"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    fault_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    maintenance_level: Mapped[str] = mapped_column(String(32), nullable=False, default="level_1")
    steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    safety_requirements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tools_required: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    materials_required: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    compliance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    executions: Mapped[list["SOPExecutionRecord"]] = relationship(back_populates="template")
    creator: Mapped["User | None"] = relationship(foreign_keys=[created_by])
    updater: Mapped["User | None"] = relationship(foreign_keys=[updated_by])

    __table_args__ = (
        Index("ix_sop_templates_manufacturer", "manufacturer"),
        Index("ix_sop_templates_product_series", "product_series"),
        Index("ix_sop_templates_device_type", "device_type"),
        Index("ix_sop_templates_fault_type", "fault_type"),
        Index("ix_sop_templates_status", "status"),
    )


class SOPExecutionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sop_execution_records"

    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id"), nullable=True)
    template_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sop_templates.id"), nullable=False)
    executor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    step_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    abnormal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    task: Mapped["MaintenanceTask | None"] = relationship(foreign_keys=[task_id])
    template: Mapped["SOPTemplate"] = relationship(back_populates="executions")
    executor: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("ix_sop_execution_records_task_id", "task_id"),
        Index("ix_sop_execution_records_template_id", "template_id"),
        Index("ix_sop_execution_records_status", "status"),
        Index("ix_sop_execution_records_executor_id", "executor_id"),
    )
