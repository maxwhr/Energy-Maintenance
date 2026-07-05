"""add_multimodal_evidence_center

Revision ID: 20260601_0006
Revises: 20260601_0005
Create Date: 2026-06-01 00:06:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0006"
down_revision: Union[str, None] = "20260601_0005"
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
        "media_processing_jobs",
        _uuid_pk(),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=128), nullable=True),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _jsonb("request_summary_json"),
        _jsonb("result_summary_json"),
        sa.Column("external_trace_id", sa.String(length=128), nullable=True),
        sa.Column("agent_run_id", sa.String(length=128), nullable=True),
        sa.Column("agent_tool_call_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["agent_tool_call_id"], ["agent_tool_calls.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["uploaded_media.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_processing_jobs_media_id", "media_processing_jobs", ["media_id"])
    op.create_index("ix_media_processing_jobs_status", "media_processing_jobs", ["status"])
    op.create_index("ix_media_processing_jobs_job_type", "media_processing_jobs", ["job_type"])
    op.create_index("ix_media_processing_jobs_provider_code", "media_processing_jobs", ["provider_code"])
    op.create_index("ix_media_processing_jobs_external_trace_id", "media_processing_jobs", ["external_trace_id"])

    op.create_table(
        "media_ocr_results",
        _uuid_pk(),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        _jsonb("regions_json"),
        _jsonb("raw_result_json"),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("external_trace_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["media_processing_jobs.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["uploaded_media.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_ocr_results_media_id", "media_ocr_results", ["media_id"])
    op.create_index("ix_media_ocr_results_job_id", "media_ocr_results", ["job_id"])
    op.create_index("ix_media_ocr_results_status", "media_ocr_results", ["status"])
    op.create_index("ix_media_ocr_results_external_trace_id", "media_ocr_results", ["external_trace_id"])

    op.create_table(
        "media_ai_analyses",
        _uuid_pk(),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("provider_name", sa.String(length=128), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("analysis_type", sa.String(length=64), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detected_text", sa.Text(), nullable=True),
        _jsonb("detected_alarm_codes_json"),
        _jsonb("detected_device_info_json"),
        _jsonb("visual_findings_json"),
        _jsonb("possible_faults_json"),
        _jsonb("safety_risks_json"),
        _jsonb("recommended_actions_json"),
        _jsonb("limitations_json"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        _jsonb("raw_response_json"),
        sa.Column("external_trace_id", sa.String(length=128), nullable=True),
        sa.Column("human_review_status", sa.String(length=32), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["media_processing_jobs.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["uploaded_media.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_ai_analyses_media_id", "media_ai_analyses", ["media_id"])
    op.create_index("ix_media_ai_analyses_job_id", "media_ai_analyses", ["job_id"])
    op.create_index("ix_media_ai_analyses_human_review_status", "media_ai_analyses", ["human_review_status"])
    op.create_index("ix_media_ai_analyses_analysis_type", "media_ai_analyses", ["analysis_type"])
    op.create_index("ix_media_ai_analyses_external_trace_id", "media_ai_analyses", ["external_trace_id"])

    op.create_table(
        "media_evidence_links",
        _uuid_pk(),
        sa.Column("media_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ocr_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        _created_at(),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["analysis_id"], ["media_ai_analyses.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["media_id"], ["uploaded_media.id"]),
        sa.ForeignKeyConstraint(["ocr_result_id"], ["media_ocr_results.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_evidence_links_media_id", "media_evidence_links", ["media_id"])
    op.create_index("ix_media_evidence_links_source", "media_evidence_links", ["source_type", "source_id"])
    op.create_index("ix_media_evidence_links_ocr_result_id", "media_evidence_links", ["ocr_result_id"])
    op.create_index("ix_media_evidence_links_analysis_id", "media_evidence_links", ["analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_media_evidence_links_analysis_id", table_name="media_evidence_links")
    op.drop_index("ix_media_evidence_links_ocr_result_id", table_name="media_evidence_links")
    op.drop_index("ix_media_evidence_links_source", table_name="media_evidence_links")
    op.drop_index("ix_media_evidence_links_media_id", table_name="media_evidence_links")
    op.drop_table("media_evidence_links")

    op.drop_index("ix_media_ai_analyses_external_trace_id", table_name="media_ai_analyses")
    op.drop_index("ix_media_ai_analyses_analysis_type", table_name="media_ai_analyses")
    op.drop_index("ix_media_ai_analyses_human_review_status", table_name="media_ai_analyses")
    op.drop_index("ix_media_ai_analyses_job_id", table_name="media_ai_analyses")
    op.drop_index("ix_media_ai_analyses_media_id", table_name="media_ai_analyses")
    op.drop_table("media_ai_analyses")

    op.drop_index("ix_media_ocr_results_external_trace_id", table_name="media_ocr_results")
    op.drop_index("ix_media_ocr_results_status", table_name="media_ocr_results")
    op.drop_index("ix_media_ocr_results_job_id", table_name="media_ocr_results")
    op.drop_index("ix_media_ocr_results_media_id", table_name="media_ocr_results")
    op.drop_table("media_ocr_results")

    op.drop_index("ix_media_processing_jobs_external_trace_id", table_name="media_processing_jobs")
    op.drop_index("ix_media_processing_jobs_provider_code", table_name="media_processing_jobs")
    op.drop_index("ix_media_processing_jobs_job_type", table_name="media_processing_jobs")
    op.drop_index("ix_media_processing_jobs_status", table_name="media_processing_jobs")
    op.drop_index("ix_media_processing_jobs_media_id", table_name="media_processing_jobs")
    op.drop_table("media_processing_jobs")
