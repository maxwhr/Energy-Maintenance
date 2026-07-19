from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MaintenanceWorkflow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_workflows"

    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("multimodal_maintenance_cases.case_id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    diagnosis_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("diagnosis_records.id"), nullable=True
    )
    diagnosis_hypothesis_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("multimodal_diagnostic_hypotheses.id"), nullable=True
    )
    sop_draft_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_artifacts.id"), nullable=True
    )
    approved_sop_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sop_templates.id"), nullable=True
    )
    task_draft_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_artifacts.id"), nullable=True
    )
    formal_task_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id"), nullable=True
    )
    record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("device_maintenance_records.id"), nullable=True
    )
    correction_candidate_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    current_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="CASE_ANALYSIS")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis_status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    diagnosis_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diagnosis_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sop_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_draft_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    diagnosis_match_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNDETERMINED")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_maintenance_workflows_case_id", "case_id"),
        Index("ix_maintenance_workflows_device_id", "device_id"),
        Index("ix_maintenance_workflows_stage", "current_stage"),
        Index("ix_maintenance_workflows_status", "status"),
        Index("ix_maintenance_workflows_formal_task_id", "formal_task_id"),
        Index("ix_maintenance_workflows_created_by", "created_by"),
        Index(
            "uq_maintenance_workflows_active_case",
            "case_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE','WAITING_USER','WAITING_ENGINEER','WAITING_EXPERT','BLOCKED')"),
        ),
    )


class MaintenanceWorkflowEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "maintenance_workflow_events"

    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("maintenance_workflows.workflow_id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id"), nullable=True)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    before_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    after_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "operation", "idempotency_key", name="uq_workflow_event_idempotency"
        ),
        Index("ix_workflow_events_workflow_id", "workflow_id"),
        Index("ix_workflow_events_case_id", "case_id"),
        Index("ix_workflow_events_task_id", "task_id"),
        Index("ix_workflow_events_event_type", "event_type"),
        Index("ix_workflow_events_created_at", "created_at"),
    )


class MaintenanceTaskStepExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "maintenance_task_step_executions"

    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("maintenance_workflows.workflow_id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False
    )
    sop_step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    performed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    is_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    is_safety_step: Mapped[bool] = mapped_column(nullable=False, default=False)
    prerequisites: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("workflow_id", "sop_step_id", name="uq_workflow_sop_step"),
        Index("ix_task_step_executions_workflow_id", "workflow_id"),
        Index("ix_task_step_executions_task_id", "task_id"),
        Index("ix_task_step_executions_status", "status"),
        Index("ix_task_step_executions_sequence", "workflow_id", "sequence"),
    )


class MaintenanceTaskExecutionRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "maintenance_task_execution_records"

    record_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("maintenance_workflows.workflow_id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False
    )
    step_execution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("maintenance_task_step_executions.id"), nullable=True
    )
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    measurements: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    parts_replaced: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    performed_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    safety_state: Mapped[str] = mapped_column(String(32), nullable=False, default="NORMAL")
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    correction_of_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("maintenance_task_execution_records.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_task_execution_records_workflow_id", "workflow_id"),
        Index("ix_task_execution_records_task_id", "task_id"),
        Index("ix_task_execution_records_step_id", "step_execution_id"),
        Index("ix_task_execution_records_record_type", "record_type"),
        Index("ix_task_execution_records_performed_at", "performed_at"),
    )
