"""add_agent_runtime_tables

Revision ID: 20260601_0004
Revises: 20260601_0003
Create Date: 2026-06-01 00:04:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0004"
down_revision: Union[str, None] = "20260601_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def _jsonb(name: str, *, nullable: bool = True) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "agent_definitions",
        _uuid_pk(),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("default_model_provider", sa.String(length=64), nullable=True),
        sa.Column("default_model_name", sa.String(length=128), nullable=True),
        _jsonb("tool_policy_json"),
        _jsonb("safety_policy_json"),
        _jsonb("metadata_json"),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_code"),
    )
    op.create_index("ix_agent_definitions_agent_type", "agent_definitions", ["agent_type"])
    op.create_index("ix_agent_definitions_enabled", "agent_definitions", ["enabled"])

    op.create_table(
        "agent_tools",
        _uuid_pk(),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_display_name", sa.String(length=128), nullable=False),
        sa.Column("tool_type", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _jsonb("allowed_roles_json"),
        _jsonb("input_schema_json"),
        _jsonb("output_schema_json"),
        sa.Column("risk_level", sa.String(length=32), nullable=True),
        _jsonb("metadata_json"),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_name"),
    )
    op.create_index("ix_agent_tools_tool_type", "agent_tools", ["tool_type"])
    op.create_index("ix_agent_tools_enabled", "agent_tools", ["enabled"])
    op.create_index("ix_agent_tools_risk_level", "agent_tools", ["risk_level"])

    op.create_table(
        "agent_runs",
        _uuid_pk(),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=True),
        _jsonb("input_media_ids_json"),
        _jsonb("context_json"),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("requires_human_approval", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_agent_runs_agent_code", "agent_runs", ["agent_code"])
    op.create_index("ix_agent_runs_user_id", "agent_runs", ["user_id"])
    op.create_index("ix_agent_runs_device_id", "agent_runs", ["device_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"])

    op.create_table(
        "agent_steps",
        _uuid_pk(),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("step_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        _jsonb("input_json"),
        _jsonb("output_json"),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_agent_steps_status", "agent_steps", ["status"])
    op.create_index("ix_agent_steps_step_index", "agent_steps", ["run_id", "step_index"])

    op.create_table(
        "agent_tool_calls",
        _uuid_pk(),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        _jsonb("input_json"),
        _jsonb("output_json"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["step_id"], ["agent_steps.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"])
    op.create_index("ix_agent_tool_calls_tool_name", "agent_tool_calls", ["tool_name"])
    op.create_index("ix_agent_tool_calls_status", "agent_tool_calls", ["status"])

    op.create_table(
        "agent_approvals",
        _uuid_pk(),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("approval_type", sa.String(length=64), nullable=False),
        sa.Column("requested_action", sa.String(length=128), nullable=False),
        _jsonb("payload_json"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_approvals_run_id", "agent_approvals", ["run_id"])
    op.create_index("ix_agent_approvals_status", "agent_approvals", ["status"])
    op.create_index("ix_agent_approvals_requested_by", "agent_approvals", ["requested_by"])
    op.create_index("ix_agent_approvals_reviewed_by", "agent_approvals", ["reviewed_by"])

    op.create_table(
        "agent_artifacts",
        _uuid_pk(),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        _jsonb("content_json"),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_artifacts_run_id", "agent_artifacts", ["run_id"])
    op.create_index("ix_agent_artifacts_artifact_type", "agent_artifacts", ["artifact_type"])
    op.create_index("ix_agent_artifacts_source", "agent_artifacts", ["source_type", "source_id"])

    op.create_table(
        "agent_event_logs",
        _uuid_pk(),
        sa.Column("run_id", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_message", sa.Text(), nullable=True),
        _jsonb("payload_json"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_event_logs_run_id", "agent_event_logs", ["run_id"])
    op.create_index("ix_agent_event_logs_event_type", "agent_event_logs", ["event_type"])
    op.create_index("ix_agent_event_logs_created_by", "agent_event_logs", ["created_by"])
    op.create_index("ix_agent_event_logs_created_at", "agent_event_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_event_logs_created_at", table_name="agent_event_logs")
    op.drop_index("ix_agent_event_logs_created_by", table_name="agent_event_logs")
    op.drop_index("ix_agent_event_logs_event_type", table_name="agent_event_logs")
    op.drop_index("ix_agent_event_logs_run_id", table_name="agent_event_logs")
    op.drop_table("agent_event_logs")

    op.drop_index("ix_agent_artifacts_source", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_artifact_type", table_name="agent_artifacts")
    op.drop_index("ix_agent_artifacts_run_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")

    op.drop_index("ix_agent_approvals_reviewed_by", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_requested_by", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_status", table_name="agent_approvals")
    op.drop_index("ix_agent_approvals_run_id", table_name="agent_approvals")
    op.drop_table("agent_approvals")

    op.drop_index("ix_agent_tool_calls_status", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_tool_name", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_run_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")

    op.drop_index("ix_agent_steps_step_index", table_name="agent_steps")
    op.drop_index("ix_agent_steps_status", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")

    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_device_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_code", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("ix_agent_tools_risk_level", table_name="agent_tools")
    op.drop_index("ix_agent_tools_enabled", table_name="agent_tools")
    op.drop_index("ix_agent_tools_tool_type", table_name="agent_tools")
    op.drop_table("agent_tools")

    op.drop_index("ix_agent_definitions_enabled", table_name="agent_definitions")
    op.drop_index("ix_agent_definitions_agent_type", table_name="agent_definitions")
    op.drop_table("agent_definitions")
