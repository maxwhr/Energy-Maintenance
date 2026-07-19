"""Allow the frozen test_v3 benchmark split.

Revision ID: 20260712_0011
Revises: 20260601_0010
Create Date: 2026-07-12 20:05:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260712_0011"
down_revision: str | None = "20260601_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_retrieval_eval_cases_split", "retrieval_evaluation_cases", type_="check")
    op.create_check_constraint(
        "ck_retrieval_eval_cases_split",
        "retrieval_evaluation_cases",
        "dataset_split in ('train','dev','test','test_v2','test_v3','engineering_train','engineering_dev','expert_review_pool','official_pilot_test')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_retrieval_eval_cases_split", "retrieval_evaluation_cases", type_="check")
    op.create_check_constraint(
        "ck_retrieval_eval_cases_split",
        "retrieval_evaluation_cases",
        "dataset_split in ('train','dev','test','test_v2','engineering_train','engineering_dev','expert_review_pool','official_pilot_test')",
    )
