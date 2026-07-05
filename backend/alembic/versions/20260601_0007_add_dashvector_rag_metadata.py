"""add dashvector rag metadata

Revision ID: 20260601_0007
Revises: 20260601_0006
Create Date: 2026-06-01 00:07:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260601_0007"
down_revision: str | None = "20260601_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunk_vector_indexes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("vector_backend", sa.String(length=64), nullable=False, server_default="dashvector"),
        sa.Column("collection_name", sa.String(length=128), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=True),
        sa.Column("vector_id", sa.String(length=256), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("index_status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "chunk_id",
            "vector_backend",
            "collection_name",
            "namespace",
            "embedding_model",
            "embedding_provider",
            name="uq_chunk_vector_index_scope",
        ),
    )
    op.create_index("ix_chunk_vector_indexes_chunk_id", "knowledge_chunk_vector_indexes", ["chunk_id"])
    op.create_index("ix_chunk_vector_indexes_document_id", "knowledge_chunk_vector_indexes", ["document_id"])
    op.create_index("ix_chunk_vector_indexes_backend", "knowledge_chunk_vector_indexes", ["vector_backend"])
    op.create_index("ix_chunk_vector_indexes_collection", "knowledge_chunk_vector_indexes", ["collection_name"])
    op.create_index("ix_chunk_vector_indexes_model", "knowledge_chunk_vector_indexes", ["embedding_model"])
    op.create_index("ix_chunk_vector_indexes_provider", "knowledge_chunk_vector_indexes", ["embedding_provider"])
    op.create_index("ix_chunk_vector_indexes_status", "knowledge_chunk_vector_indexes", ["index_status"])
    op.create_index("ix_chunk_vector_indexes_content_hash", "knowledge_chunk_vector_indexes", ["content_hash"])
    op.create_index("ix_chunk_vector_indexes_last_indexed_at", "knowledge_chunk_vector_indexes", ["last_indexed_at"])

    op.create_table(
        "vector_index_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vector_backend", sa.String(length=64), nullable=False, server_default="dashvector"),
        sa.Column("collection_name", sa.String(length=128), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vector_index_runs_run_type", "vector_index_runs", ["run_type"])
    op.create_index("ix_vector_index_runs_target", "vector_index_runs", ["target_type", "target_id"])
    op.create_index("ix_vector_index_runs_backend", "vector_index_runs", ["vector_backend"])
    op.create_index("ix_vector_index_runs_status", "vector_index_runs", ["status"])
    op.create_index("ix_vector_index_runs_created_at", "vector_index_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_vector_index_runs_created_at", table_name="vector_index_runs")
    op.drop_index("ix_vector_index_runs_status", table_name="vector_index_runs")
    op.drop_index("ix_vector_index_runs_backend", table_name="vector_index_runs")
    op.drop_index("ix_vector_index_runs_target", table_name="vector_index_runs")
    op.drop_index("ix_vector_index_runs_run_type", table_name="vector_index_runs")
    op.drop_table("vector_index_runs")

    op.drop_index("ix_chunk_vector_indexes_last_indexed_at", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_content_hash", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_status", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_provider", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_model", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_collection", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_backend", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_document_id", table_name="knowledge_chunk_vector_indexes")
    op.drop_index("ix_chunk_vector_indexes_chunk_id", table_name="knowledge_chunk_vector_indexes")
    op.drop_table("knowledge_chunk_vector_indexes")
