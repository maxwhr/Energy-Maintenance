from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import KnowledgeContribution, KnowledgeReviewRecord


class KnowledgeContributionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, contribution: KnowledgeContribution) -> KnowledgeContribution:
        self.db.add(contribution)
        self.db.flush()
        self.db.refresh(contribution)
        return contribution

    def update(self, contribution: KnowledgeContribution) -> KnowledgeContribution:
        self.db.add(contribution)
        self.db.flush()
        self.db.refresh(contribution)
        return contribution

    def get_by_id(self, contribution_id: UUID) -> KnowledgeContribution | None:
        statement = (
            select(KnowledgeContribution)
            .options(
                selectinload(KnowledgeContribution.submitter),
                selectinload(KnowledgeContribution.device),
                selectinload(KnowledgeContribution.approved_document),
                selectinload(KnowledgeContribution.review_records),
            )
            .where(KnowledgeContribution.id == contribution_id)
        )
        return self.db.scalar(statement)

    def list(
        self,
        *,
        filters: list[Any],
        page: int,
        page_size: int,
    ) -> tuple[list[KnowledgeContribution], int]:
        count_statement = select(func.count()).select_from(KnowledgeContribution)
        list_statement = (
            select(KnowledgeContribution)
            .options(
                selectinload(KnowledgeContribution.submitter),
                selectinload(KnowledgeContribution.device),
                selectinload(KnowledgeContribution.approved_document),
            )
            .order_by(KnowledgeContribution.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        return list(self.db.scalars(list_statement)), total

    def build_filters(
        self,
        *,
        review_status: str | None = None,
        contribution_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_id: UUID | None = None,
        submitted_by: UUID | None = None,
        keyword: str | None = None,
        visible_statuses: set[str] | None = None,
        owner_or_public_user_id: UUID | None = None,
    ) -> list[Any]:
        filters: list[Any] = []
        if visible_statuses and owner_or_public_user_id:
            filters.append(
                or_(
                    KnowledgeContribution.submitted_by == owner_or_public_user_id,
                    KnowledgeContribution.review_status.in_(visible_statuses),
                )
            )
        elif visible_statuses:
            filters.append(KnowledgeContribution.review_status.in_(visible_statuses))

        if review_status:
            filters.append(KnowledgeContribution.review_status == review_status)
        if contribution_type:
            filters.append(KnowledgeContribution.contribution_type == contribution_type)
        if manufacturer:
            filters.append(KnowledgeContribution.manufacturer == manufacturer)
        if product_series:
            filters.append(KnowledgeContribution.product_series == product_series)
        if device_id:
            filters.append(KnowledgeContribution.device_id == device_id)
        if submitted_by:
            filters.append(KnowledgeContribution.submitted_by == submitted_by)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeContribution.title.ilike(pattern),
                    KnowledgeContribution.content.ilike(pattern),
                    KnowledgeContribution.source_trace_id.ilike(pattern),
                    KnowledgeContribution.review_comment.ilike(pattern),
                )
            )
        return filters

    def add_review_record(self, record: KnowledgeReviewRecord) -> KnowledgeReviewRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_review_records(self, contribution_id: UUID) -> list[KnowledgeReviewRecord]:
        statement = (
            select(KnowledgeReviewRecord)
            .where(KnowledgeReviewRecord.contribution_id == contribution_id)
            .order_by(KnowledgeReviewRecord.reviewed_at.desc(), KnowledgeReviewRecord.created_at.desc())
        )
        return list(self.db.scalars(statement))
