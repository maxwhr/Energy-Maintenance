"""Add high precision RAG evaluation and media similarity tables.

Revision ID: 20260601_0009
Revises: 20260601_0008
Create Date: 2026-06-01 00:09:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0009"
down_revision: str | None = "20260601_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "retrieval_evaluation_cases",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("query_media_id", uuid, sa.ForeignKey("uploaded_media.id", ondelete="SET NULL")),
        sa.Column("expected_document_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("expected_chunk_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("expected_media_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("required_filters", jsonb, nullable=False, server_default="{}"),
        sa.Column("excluded_document_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("difficulty", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("dataset_split", sa.String(16), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("metadata_json", jsonb),
        sa.Column("created_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.CheckConstraint("dataset_split in ('train','dev','test')", name="ck_retrieval_eval_cases_split"),
        sa.CheckConstraint("review_status in ('draft','engineering_verified','expert_verified','rejected')", name="ck_retrieval_eval_cases_review"),
    )
    for name, cols in (
        ("ix_retrieval_eval_cases_category", ["category"]),
        ("ix_retrieval_eval_cases_split", ["dataset_split"]),
        ("ix_retrieval_eval_cases_review", ["review_status"]),
        ("ix_retrieval_eval_cases_source", ["source_type"]),
    ):
        op.create_index(name, "retrieval_evaluation_cases", cols)

    op.create_table(
        "retrieval_evaluation_runs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("embedding_provider", sa.String(64), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("vector_backend", sa.String(64), nullable=False),
        sa.Column("collection_name", sa.String(128), nullable=False),
        sa.Column("retrieval_config_json", jsonb, nullable=False, server_default="{}"),
        sa.Column("dataset_version", sa.String(64), nullable=False),
        sa.Column("run_status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("metrics_json", jsonb),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_by", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("run_status in ('pending','running','succeeded','partial_failed','failed')", name="ck_retrieval_eval_runs_status"),
    )
    op.create_index("ix_retrieval_eval_runs_status", "retrieval_evaluation_runs", ["run_status"])
    op.create_index("ix_retrieval_eval_runs_dataset", "retrieval_evaluation_runs", ["dataset_version"])
    op.create_index("ix_retrieval_eval_runs_created", "retrieval_evaluation_runs", ["created_at"])

    op.create_table(
        "retrieval_evaluation_results",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("run_id", uuid, sa.ForeignKey("retrieval_evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", uuid, sa.ForeignKey("retrieval_evaluation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retrieval_mode", sa.String(64), nullable=False),
        sa.Column("ranked_document_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("ranked_chunk_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("ranked_media_ids", jsonb, nullable=False, server_default="[]"),
        sa.Column("score_breakdown_json", jsonb, nullable=False, server_default="{}"),
        sa.Column("recall_at_5", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recall_at_10", sa.Float(), nullable=False, server_default="0"),
        sa.Column("reciprocal_rank", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ndcg_at_10", sa.Float(), nullable=False, server_default="0"),
        sa.Column("precision_at_5", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "case_id", "retrieval_mode", name="uq_retrieval_eval_result_scope"),
    )
    op.create_index("ix_retrieval_eval_results_run", "retrieval_evaluation_results", ["run_id"])
    op.create_index("ix_retrieval_eval_results_case", "retrieval_evaluation_results", ["case_id"])
    op.create_index("ix_retrieval_eval_results_mode", "retrieval_evaluation_results", ["retrieval_mode"])

    op.create_table(
        "media_similarity_features",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("media_id", uuid, sa.ForeignKey("uploaded_media.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("perceptual_hash", sa.String(128), nullable=False),
        sa.Column("difference_hash", sa.String(128), nullable=False),
        sa.Column("ocr_normalized_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("visual_descriptor", sa.Text(), nullable=False),
        sa.Column("device_model", sa.String(128)),
        sa.Column("fault_codes", jsonb, nullable=False, server_default="[]"),
        sa.Column("component_tags", jsonb, nullable=False, server_default="[]"),
        sa.Column("vector_index_id", sa.String(256)),
        sa.Column("embedding_model", sa.String(128)),
        sa.Column("embedding_dimension", sa.Integer()),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("feature_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("metadata_json", jsonb),
        *_timestamps(),
    )
    op.create_index("ix_media_similarity_features_status", "media_similarity_features", ["feature_status"])
    op.create_index("ix_media_similarity_features_hash", "media_similarity_features", ["content_hash"])
    op.create_index("ix_media_similarity_features_model", "media_similarity_features", ["device_model"])


def downgrade() -> None:
    op.drop_table("media_similarity_features")
    op.drop_table("retrieval_evaluation_results")
    op.drop_table("retrieval_evaluation_runs")
    op.drop_table("retrieval_evaluation_cases")
