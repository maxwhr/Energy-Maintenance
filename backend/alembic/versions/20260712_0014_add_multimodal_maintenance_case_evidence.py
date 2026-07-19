"""add multimodal maintenance case evidence chain

Revision ID: 20260712_0014
Revises: 20260712_0013
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260712_0014"
down_revision = "20260712_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "multimodal_maintenance_cases",
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("user_query", sa.Text(), nullable=True),
        sa.Column("normalized_query", sa.Text(), nullable=True),
        sa.Column("conversation_id", sa.String(length=128), nullable=True),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("device_model", sa.String(length=128), nullable=True),
        sa.Column("product_family", sa.String(length=128), nullable=True),
        sa.Column("equipment_category", sa.String(length=64), nullable=True),
        sa.Column("alarm_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reported_symptoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurrence_conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_confirmed_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("clarifying_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("media_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("knowledge_citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("safety_level", sa.String(length=32), nullable=False),
        sa.Column("confidence_status", sa.String(length=32), nullable=False),
        sa.Column("diagnosis_status", sa.String(length=32), nullable=False),
        sa.Column("sop_draft_id", sa.Uuid(), nullable=True),
        sa.Column("task_draft_id", sa.Uuid(), nullable=True),
        sa.Column("analysis_job_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_error_code", sa.String(length=128), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["sop_draft_id"], ["agent_artifacts.id"]),
        sa.ForeignKeyConstraint(["task_draft_id"], ["agent_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_multimodal_cases_status", "multimodal_maintenance_cases", ["status"])
    op.create_index("ix_multimodal_cases_created_by", "multimodal_maintenance_cases", ["created_by"])
    op.create_index("ix_multimodal_cases_device_id", "multimodal_maintenance_cases", ["device_id"])
    op.create_index("ix_multimodal_cases_conversation_id", "multimodal_maintenance_cases", ["conversation_id"])

    op.create_table(
        "multimodal_evidence_items",
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=True),
        sa.Column("ocr_result_id", sa.Uuid(), nullable=True),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("frame_id", sa.String(length=128), nullable=True),
        sa.Column("region_id", sa.String(length=128), nullable=True),
        sa.Column("modality", sa.String(length=32), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("observed_text", sa.Text(), nullable=True),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("visual_attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("page_or_frame_locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("device_model_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("alarm_code_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("component_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("indicator_state_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("symptom_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("observation_status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_model", sa.String(length=128), nullable=True),
        sa.Column("provider_trace_id", sa.String(length=128), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("contradicted", sa.Boolean(), nullable=False),
        sa.Column("contradiction_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["media_ai_analyses.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["multimodal_maintenance_cases.case_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["uploaded_media.id"]),
        sa.ForeignKeyConstraint(["ocr_result_id"], ["media_ocr_results.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "source_hash", "evidence_type", name="uq_multimodal_evidence_identity"),
        sa.UniqueConstraint("evidence_id"),
    )
    op.create_index("ix_multimodal_evidence_case_id", "multimodal_evidence_items", ["case_id"])
    op.create_index("ix_multimodal_evidence_media_id", "multimodal_evidence_items", ["media_id"])
    op.create_index("ix_multimodal_evidence_status", "multimodal_evidence_items", ["observation_status"])
    op.create_index("ix_multimodal_evidence_region_id", "multimodal_evidence_items", ["region_id"])

    op.create_table(
        "multimodal_evidence_conflicts",
        sa.Column("conflict_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("conflict_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("resolution_required", sa.Boolean(), nullable=False),
        sa.Column("recommended_question", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolution_status", sa.String(length=32), nullable=False),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["multimodal_maintenance_cases.case_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conflict_id"),
    )
    op.create_index("ix_multimodal_conflicts_case_id", "multimodal_evidence_conflicts", ["case_id"])
    op.create_index("ix_multimodal_conflicts_status", "multimodal_evidence_conflicts", ["resolution_status"])
    op.create_index("ix_multimodal_conflicts_severity", "multimodal_evidence_conflicts", ["severity"])

    op.create_table(
        "multimodal_diagnostic_hypotheses",
        sa.Column("hypothesis_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("fault_category", sa.String(length=64), nullable=False),
        sa.Column("fault_name", sa.String(length=255), nullable=False),
        sa.Column("applicable_device", sa.String(length=128), nullable=True),
        sa.Column("required_conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supporting_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contradicting_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("knowledge_citation_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confidence_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommended_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("safety_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["multimodal_maintenance_cases.case_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hypothesis_id"),
    )
    op.create_index("ix_multimodal_hypotheses_case_id", "multimodal_diagnostic_hypotheses", ["case_id"])
    op.create_index("ix_multimodal_hypotheses_status", "multimodal_diagnostic_hypotheses", ["status"])
    op.create_index("ix_multimodal_hypotheses_fault_category", "multimodal_diagnostic_hypotheses", ["fault_category"])


def downgrade() -> None:
    op.drop_index("ix_multimodal_hypotheses_fault_category", table_name="multimodal_diagnostic_hypotheses")
    op.drop_index("ix_multimodal_hypotheses_status", table_name="multimodal_diagnostic_hypotheses")
    op.drop_index("ix_multimodal_hypotheses_case_id", table_name="multimodal_diagnostic_hypotheses")
    op.drop_table("multimodal_diagnostic_hypotheses")
    op.drop_index("ix_multimodal_conflicts_severity", table_name="multimodal_evidence_conflicts")
    op.drop_index("ix_multimodal_conflicts_status", table_name="multimodal_evidence_conflicts")
    op.drop_index("ix_multimodal_conflicts_case_id", table_name="multimodal_evidence_conflicts")
    op.drop_table("multimodal_evidence_conflicts")
    op.drop_index("ix_multimodal_evidence_region_id", table_name="multimodal_evidence_items")
    op.drop_index("ix_multimodal_evidence_status", table_name="multimodal_evidence_items")
    op.drop_index("ix_multimodal_evidence_media_id", table_name="multimodal_evidence_items")
    op.drop_index("ix_multimodal_evidence_case_id", table_name="multimodal_evidence_items")
    op.drop_table("multimodal_evidence_items")
    op.drop_index("ix_multimodal_cases_conversation_id", table_name="multimodal_maintenance_cases")
    op.drop_index("ix_multimodal_cases_device_id", table_name="multimodal_maintenance_cases")
    op.drop_index("ix_multimodal_cases_created_by", table_name="multimodal_maintenance_cases")
    op.drop_index("ix_multimodal_cases_status", table_name="multimodal_maintenance_cases")
    op.drop_table("multimodal_maintenance_cases")
