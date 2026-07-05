"""Add agent artifact conversion audit table.

Revision ID: 20260601_0008
Revises: 20260601_0007
Create Date: 2026-06-01 00:08:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260601_0008"
down_revision: str | None = "20260601_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_artifact_conversions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_artifact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_artifacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_approval_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_approvals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_table", sa.String(length=128), nullable=True),
        sa.Column("conversion_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("conversion_trace_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("converted_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("voided_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_artifact_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("target_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_artifact_id", "target_type", name="uq_agent_artifact_conversions_artifact_target"),
    )
    op.create_index("ix_agent_artifact_conversions_source_run_id", "agent_artifact_conversions", ["source_run_id"])
    op.create_index("ix_agent_artifact_conversions_source_artifact_id", "agent_artifact_conversions", ["source_artifact_id"])
    op.create_index("ix_agent_artifact_conversions_source_approval_id", "agent_artifact_conversions", ["source_approval_id"])
    op.create_index("ix_agent_artifact_conversions_target_type", "agent_artifact_conversions", ["target_type"])
    op.create_index("ix_agent_artifact_conversions_target_id", "agent_artifact_conversions", ["target_id"])
    op.create_index("ix_agent_artifact_conversions_conversion_status", "agent_artifact_conversions", ["conversion_status"])
    op.create_index("ix_agent_artifact_conversions_conversion_trace_id", "agent_artifact_conversions", ["conversion_trace_id"])
    op.create_index("ix_agent_artifact_conversions_requested_by", "agent_artifact_conversions", ["requested_by"])
    op.create_index("ix_agent_artifact_conversions_converted_by", "agent_artifact_conversions", ["converted_by"])
    op.create_index("ix_agent_artifact_conversions_created_at", "agent_artifact_conversions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_artifact_conversions_created_at", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_converted_by", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_requested_by", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_conversion_trace_id", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_conversion_status", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_target_id", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_target_type", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_source_approval_id", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_source_artifact_id", table_name="agent_artifact_conversions")
    op.drop_index("ix_agent_artifact_conversions_source_run_id", table_name="agent_artifact_conversions")
    op.drop_table("agent_artifact_conversions")
