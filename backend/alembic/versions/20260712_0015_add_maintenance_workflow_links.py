"""add maintenance workflow links, events, task steps, and execution records

Revision ID: 20260712_0015
Revises: 20260712_0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260712_0015"
down_revision = "20260712_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "maintenance_workflows",
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("diagnosis_id", sa.Uuid(), nullable=True),
        sa.Column("diagnosis_hypothesis_id", sa.Uuid(), nullable=True),
        sa.Column("sop_draft_id", sa.Uuid(), nullable=True),
        sa.Column("approved_sop_id", sa.Uuid(), nullable=True),
        sa.Column("task_draft_id", sa.Uuid(), nullable=True),
        sa.Column("formal_task_id", sa.Uuid(), nullable=True),
        sa.Column("record_id", sa.Uuid(), nullable=True),
        sa.Column("correction_candidate_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column("required_action", sa.Text(), nullable=True),
        sa.Column("diagnosis_status", sa.String(length=32), nullable=False),
        sa.Column("diagnosis_version", sa.Integer(), nullable=False),
        sa.Column("diagnosis_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sop_version", sa.Integer(), nullable=False),
        sa.Column("task_draft_version", sa.Integer(), nullable=False),
        sa.Column("actual_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diagnosis_match_status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lock_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_sop_id"], ["sop_templates.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["multimodal_maintenance_cases.case_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["diagnosis_hypothesis_id"], ["multimodal_diagnostic_hypotheses.id"]),
        sa.ForeignKeyConstraint(["diagnosis_id"], ["diagnosis_records.id"]),
        sa.ForeignKeyConstraint(["formal_task_id"], ["maintenance_tasks.id"]),
        sa.ForeignKeyConstraint(["record_id"], ["device_maintenance_records.id"]),
        sa.ForeignKeyConstraint(["sop_draft_id"], ["agent_artifacts.id"]),
        sa.ForeignKeyConstraint(["task_draft_id"], ["agent_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_index("ix_maintenance_workflows_case_id", "maintenance_workflows", ["case_id"])
    op.create_index("ix_maintenance_workflows_device_id", "maintenance_workflows", ["device_id"])
    op.create_index("ix_maintenance_workflows_stage", "maintenance_workflows", ["current_stage"])
    op.create_index("ix_maintenance_workflows_status", "maintenance_workflows", ["status"])
    op.create_index("ix_maintenance_workflows_formal_task_id", "maintenance_workflows", ["formal_task_id"])
    op.create_index("ix_maintenance_workflows_created_by", "maintenance_workflows", ["created_by"])
    op.create_index(
        "uq_maintenance_workflows_active_case",
        "maintenance_workflows",
        ["case_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('ACTIVE','WAITING_USER','WAITING_ENGINEER','WAITING_EXPERT','BLOCKED')"
        ),
    )

    op.create_table(
        "maintenance_workflow_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"]),
        sa.ForeignKeyConstraint(["workflow_id"], ["maintenance_workflows.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
        sa.UniqueConstraint("workflow_id", "operation", "idempotency_key", name="uq_workflow_event_idempotency"),
    )
    op.create_index("ix_workflow_events_workflow_id", "maintenance_workflow_events", ["workflow_id"])
    op.create_index("ix_workflow_events_case_id", "maintenance_workflow_events", ["case_id"])
    op.create_index("ix_workflow_events_task_id", "maintenance_workflow_events", ["task_id"])
    op.create_index("ix_workflow_events_event_type", "maintenance_workflow_events", ["event_type"])
    op.create_index("ix_workflow_events_created_at", "maintenance_workflow_events", ["created_at"])

    op.create_table(
        "maintenance_task_step_executions",
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("sop_step_id", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performed_by", sa.Uuid(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_safety_step", sa.Boolean(), nullable=False),
        sa.Column("prerequisites", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["maintenance_workflows.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "sop_step_id", name="uq_workflow_sop_step"),
    )
    op.create_index("ix_task_step_executions_workflow_id", "maintenance_task_step_executions", ["workflow_id"])
    op.create_index("ix_task_step_executions_task_id", "maintenance_task_step_executions", ["task_id"])
    op.create_index("ix_task_step_executions_status", "maintenance_task_step_executions", ["status"])
    op.create_index("ix_task_step_executions_sequence", "maintenance_task_step_executions", ["workflow_id", "sequence"])

    op.create_table(
        "maintenance_task_execution_records",
        sa.Column("record_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("step_execution_id", sa.Uuid(), nullable=True),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("media_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("measurements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("parts_replaced", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("performed_by", sa.Uuid(), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("safety_state", sa.String(length=32), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("correction_of_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["correction_of_id"], ["maintenance_task_execution_records.id"]),
        sa.ForeignKeyConstraint(["performed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["step_execution_id"], ["maintenance_task_step_executions.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["maintenance_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["maintenance_workflows.workflow_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id"),
    )
    op.create_index("ix_task_execution_records_workflow_id", "maintenance_task_execution_records", ["workflow_id"])
    op.create_index("ix_task_execution_records_task_id", "maintenance_task_execution_records", ["task_id"])
    op.create_index("ix_task_execution_records_step_id", "maintenance_task_execution_records", ["step_execution_id"])
    op.create_index("ix_task_execution_records_record_type", "maintenance_task_execution_records", ["record_type"])
    op.create_index("ix_task_execution_records_performed_at", "maintenance_task_execution_records", ["performed_at"])


def downgrade() -> None:
    op.drop_index("ix_task_execution_records_performed_at", table_name="maintenance_task_execution_records")
    op.drop_index("ix_task_execution_records_record_type", table_name="maintenance_task_execution_records")
    op.drop_index("ix_task_execution_records_step_id", table_name="maintenance_task_execution_records")
    op.drop_index("ix_task_execution_records_task_id", table_name="maintenance_task_execution_records")
    op.drop_index("ix_task_execution_records_workflow_id", table_name="maintenance_task_execution_records")
    op.drop_table("maintenance_task_execution_records")
    op.drop_index("ix_task_step_executions_sequence", table_name="maintenance_task_step_executions")
    op.drop_index("ix_task_step_executions_status", table_name="maintenance_task_step_executions")
    op.drop_index("ix_task_step_executions_task_id", table_name="maintenance_task_step_executions")
    op.drop_index("ix_task_step_executions_workflow_id", table_name="maintenance_task_step_executions")
    op.drop_table("maintenance_task_step_executions")
    op.drop_index("ix_workflow_events_created_at", table_name="maintenance_workflow_events")
    op.drop_index("ix_workflow_events_event_type", table_name="maintenance_workflow_events")
    op.drop_index("ix_workflow_events_task_id", table_name="maintenance_workflow_events")
    op.drop_index("ix_workflow_events_case_id", table_name="maintenance_workflow_events")
    op.drop_index("ix_workflow_events_workflow_id", table_name="maintenance_workflow_events")
    op.drop_table("maintenance_workflow_events")
    op.drop_index("uq_maintenance_workflows_active_case", table_name="maintenance_workflows")
    op.drop_index("ix_maintenance_workflows_created_by", table_name="maintenance_workflows")
    op.drop_index("ix_maintenance_workflows_formal_task_id", table_name="maintenance_workflows")
    op.drop_index("ix_maintenance_workflows_status", table_name="maintenance_workflows")
    op.drop_index("ix_maintenance_workflows_stage", table_name="maintenance_workflows")
    op.drop_index("ix_maintenance_workflows_device_id", table_name="maintenance_workflows")
    op.drop_index("ix_maintenance_workflows_case_id", table_name="maintenance_workflows")
    op.drop_table("maintenance_workflows")
