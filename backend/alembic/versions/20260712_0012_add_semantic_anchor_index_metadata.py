"""Add isolated maintenance semantic-anchor mapping metadata.

Revision ID: 20260712_0012
Revises: 20260712_0011
Create Date: 2026-07-13 10:58:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260712_0012"
down_revision: str | None = "20260712_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_semantic_anchors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_name", sa.String(length=128), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=False),
        sa.Column("anchor_type", sa.String(length=32), nullable=False),
        sa.Column("anchor_text", sa.Text(), nullable=False),
        sa.Column("anchor_text_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical_retrieval_text", sa.Text(), nullable=False),
        sa.Column("semantic_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("semantic_representation_hash", sa.String(length=64), nullable=False),
        sa.Column("semantic_representation_version", sa.String(length=64), nullable=False),
        sa.Column("source_locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("approval_mode", sa.String(length=64), nullable=True),
        sa.Column("current_version", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("vector_id", sa.String(length=256), nullable=False),
        sa.Column("embedding_provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("index_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("index_content_hash", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["knowledge_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_chunk_id", "anchor_type", "semantic_representation_version", "collection_name", "namespace", name="uq_semantic_anchor_source_type_version_scope"),
    )
    op.create_index("ix_semantic_anchor_scope", "maintenance_semantic_anchors", ["collection_name", "namespace", "index_status"])
    op.create_index("ix_semantic_anchor_vector", "maintenance_semantic_anchors", ["vector_id"])
    op.create_index("ix_semantic_anchor_source", "maintenance_semantic_anchors", ["source_chunk_id"])
    op.create_index("ix_semantic_anchor_hash", "maintenance_semantic_anchors", ["semantic_representation_hash"])


def downgrade() -> None:
    op.drop_table("maintenance_semantic_anchors")
