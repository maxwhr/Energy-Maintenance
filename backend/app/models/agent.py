from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_definitions"

    agent_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    agent_name: Mapped[str] = mapped_column(String(128), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_policy_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    safety_policy_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_agent_definitions_agent_type", "agent_type"),
        Index("ix_agent_definitions_enabled", "enabled"),
    )


class AgentTool(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_tools"

    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    tool_display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_roles_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    input_schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_agent_tools_tool_type", "tool_type"),
        Index("ix_agent_tools_enabled", "enabled"),
        Index("ix_agent_tools_risk_level", "risk_level"),
    )


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    agent_code: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_media_ids_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    context_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approval_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_agent_runs_agent_code", "agent_code"),
        Index("ix_agent_runs_user_id", "user_id"),
        Index("ix_agent_runs_device_id", "device_id"),
        Index("ix_agent_runs_status", "status"),
        Index("ix_agent_runs_created_at", "created_at"),
    )


class AgentStep(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_steps"

    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_agent_steps_run_id", "run_id"),
        Index("ix_agent_steps_status", "status"),
        Index("ix_agent_steps_step_index", "run_id", "step_index"),
    )


class AgentToolCall(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_tool_calls"

    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("agent_steps.id"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_agent_tool_calls_run_id", "run_id"),
        Index("ix_agent_tool_calls_tool_name", "tool_name"),
        Index("ix_agent_tool_calls_status", "status"),
    )


class AgentApproval(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_approvals"

    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_agent_approvals_run_id", "run_id"),
        Index("ix_agent_approvals_status", "status"),
        Index("ix_agent_approvals_requested_by", "requested_by"),
        Index("ix_agent_approvals_reviewed_by", "reviewed_by"),
    )


class AgentArtifact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_artifacts"

    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_agent_artifacts_run_id", "run_id"),
        Index("ix_agent_artifacts_artifact_type", "artifact_type"),
        Index("ix_agent_artifacts_source", "source_type", "source_id"),
    )


class AgentArtifactConversion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_artifact_conversions"

    source_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_artifact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_approval_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agent_approvals.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    target_table: Mapped[str | None] = mapped_column(String(128), nullable=True)
    conversion_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    conversion_trace_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    requested_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    converted_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    voided_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    request_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_artifact_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    target_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("source_artifact_id", "target_type", name="uq_agent_artifact_conversions_artifact_target"),
        Index("ix_agent_artifact_conversions_source_run_id", "source_run_id"),
        Index("ix_agent_artifact_conversions_source_artifact_id", "source_artifact_id"),
        Index("ix_agent_artifact_conversions_source_approval_id", "source_approval_id"),
        Index("ix_agent_artifact_conversions_target_type", "target_type"),
        Index("ix_agent_artifact_conversions_target_id", "target_id"),
        Index("ix_agent_artifact_conversions_conversion_status", "conversion_status"),
        Index("ix_agent_artifact_conversions_conversion_trace_id", "conversion_trace_id"),
        Index("ix_agent_artifact_conversions_requested_by", "requested_by"),
        Index("ix_agent_artifact_conversions_converted_by", "converted_by"),
        Index("ix_agent_artifact_conversions_created_at", "created_at"),
    )


class AgentEventLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_event_logs"

    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_agent_event_logs_run_id", "run_id"),
        Index("ix_agent_event_logs_event_type", "event_type"),
        Index("ix_agent_event_logs_created_by", "created_by"),
        Index("ix_agent_event_logs_created_at", "created_at"),
    )
