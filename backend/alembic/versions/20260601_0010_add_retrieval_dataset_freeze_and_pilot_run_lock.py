"""Add retrieval dataset freeze and official Pilot run lock.

Revision ID: 20260601_0010
Revises: 20260601_0009
Create Date: 2026-06-01 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260601_0010"
down_revision: str | None = "20260601_0009"
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

    op.drop_constraint("ck_retrieval_eval_cases_split", "retrieval_evaluation_cases", type_="check")
    op.drop_constraint("ck_retrieval_eval_cases_review", "retrieval_evaluation_cases", type_="check")
    op.alter_column(
        "retrieval_evaluation_cases",
        "dataset_split",
        existing_type=sa.String(16),
        type_=sa.String(32),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_retrieval_eval_cases_split",
        "retrieval_evaluation_cases",
        "dataset_split in ('train','dev','test','test_v2','engineering_train','engineering_dev','expert_review_pool','official_pilot_test')",
    )
    op.create_check_constraint(
        "ck_retrieval_eval_cases_review",
        "retrieval_evaluation_cases",
        "review_status in ('draft','engineering_verified','expert_review_pending','expert_verified','expert_rejected','needs_revision','rejected')",
    )

    op.create_table(
        "retrieval_dataset_freezes",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("dataset_version", sa.String(64), nullable=False, unique=True),
        sa.Column("dataset_type", sa.String(64), nullable=False),
        sa.Column("dataset_sha256", sa.String(64), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("freeze_status", sa.String(32), nullable=False, server_default="frozen"),
        sa.Column("frozen_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unfrozen_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("unfrozen_at", sa.DateTime(timezone=True)),
        sa.Column("unfreeze_reason", sa.Text()),
        sa.Column("metadata_json", jsonb, nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_retrieval_dataset_freezes_status", "retrieval_dataset_freezes", ["freeze_status"])
    op.create_index("ix_retrieval_dataset_freezes_type", "retrieval_dataset_freezes", ["dataset_type"])

    op.create_table(
        "retrieval_official_run_locks",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "dataset_freeze_id", uuid,
            sa.ForeignKey("retrieval_dataset_freezes.id", ondelete="RESTRICT"), nullable=False,
        ),
        sa.Column("run_purpose", sa.String(64), nullable=False),
        sa.Column(
            "official_run_id", uuid,
            sa.ForeignKey("retrieval_evaluation_runs.id", ondelete="RESTRICT"),
        ),
        sa.Column("lock_status", sa.String(32), nullable=False, server_default="locked"),
        sa.Column("locked_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_sha256", sa.String(64)),
        sa.Column("unlock_requested_by", uuid, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("unlock_reason", sa.Text()),
        sa.Column("metadata_json", jsonb, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint(
            "dataset_freeze_id", "run_purpose", name="uq_retrieval_official_run_lock_scope"
        ),
    )
    op.create_index("ix_retrieval_official_run_locks_status", "retrieval_official_run_locks", ["lock_status"])
    op.create_index("ix_retrieval_official_run_locks_freeze", "retrieval_official_run_locks", ["dataset_freeze_id"])


def downgrade() -> None:
    op.drop_table("retrieval_official_run_locks")
    op.drop_table("retrieval_dataset_freezes")
    op.drop_constraint("ck_retrieval_eval_cases_review", "retrieval_evaluation_cases", type_="check")
    op.drop_constraint("ck_retrieval_eval_cases_split", "retrieval_evaluation_cases", type_="check")
    op.alter_column(
        "retrieval_evaluation_cases",
        "dataset_split",
        existing_type=sa.String(32),
        type_=sa.String(16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_retrieval_eval_cases_review",
        "retrieval_evaluation_cases",
        "review_status in ('draft','engineering_verified','expert_verified','rejected')",
    )
    op.create_check_constraint(
        "ck_retrieval_eval_cases_split",
        "retrieval_evaluation_cases",
        "dataset_split in ('train','dev','test')",
    )
