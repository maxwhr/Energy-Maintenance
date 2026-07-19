"""add query-aware RAG conversation support

Revision ID: 20260712_0013
Revises: 20260712_0012
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260712_0013"
down_revision = "20260712_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "query_aware_retrieval_sessions",
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("original_query", sa.Text(), nullable=False),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
    )
    op.create_index("ix_query_aware_sessions_status", "query_aware_retrieval_sessions", ["status"])
    op.create_index("ix_query_aware_sessions_expires", "query_aware_retrieval_sessions", ["expires_at"])
    op.create_index("ix_query_aware_sessions_created_by", "query_aware_retrieval_sessions", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_query_aware_sessions_created_by", table_name="query_aware_retrieval_sessions")
    op.drop_index("ix_query_aware_sessions_expires", table_name="query_aware_retrieval_sessions")
    op.drop_index("ix_query_aware_sessions_status", table_name="query_aware_retrieval_sessions")
    op.drop_table("query_aware_retrieval_sessions")
