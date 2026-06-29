from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeReviewRecord, User


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_documents(
        self,
        *,
        review_status: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        document_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeDocument], int]:
        filters = []
        if review_status:
            filters.append(KnowledgeDocument.review_status == review_status)
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series:
            filters.append(KnowledgeDocument.product_series == product_series)
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.summary.ilike(pattern),
                    KnowledgeDocument.source.ilike(pattern),
                    KnowledgeDocument.file_name.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(KnowledgeDocument)
        list_statement = select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        documents = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return documents, total

    def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        return self.db.get(KnowledgeDocument, document_id)

    def list_chunk_preview(self, document_id: UUID, limit: int = 5) -> list[KnowledgeChunk]:
        statement = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def list_review_records(self, document_id: UUID) -> list[KnowledgeReviewRecord]:
        statement = (
            select(KnowledgeReviewRecord)
            .where(KnowledgeReviewRecord.document_id == document_id)
            .order_by(KnowledgeReviewRecord.reviewed_at.desc().nullslast(), KnowledgeReviewRecord.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def update_document_review(
        self,
        *,
        document: KnowledgeDocument,
        action: str,
        after_status: str,
        reviewer: User,
        comment: str | None,
        archive_status: bool = False,
    ) -> tuple[KnowledgeDocument, KnowledgeReviewRecord]:
        before_status = document.review_status
        document.review_status = after_status
        document.reviewed_by = reviewer.id
        document.reviewed_at = datetime.now(timezone.utc)
        document.review_comment = comment
        if archive_status:
            document.status = "archived"
        self.db.add(document)
        review_record = KnowledgeReviewRecord(
            document_id=document.id,
            reviewer_id=reviewer.id,
            review_action=action,
            review_comment=comment,
            before_status=before_status,
            after_status=after_status,
            reviewed_at=datetime.now(timezone.utc),
            metadata_json={"document_title": document.title},
        )
        self.db.add(review_record)
        self.db.flush()
        self.db.refresh(document)
        self.db.refresh(review_record)
        return document, review_record

    def get_user(self, user_id: UUID | None) -> User | None:
        if not user_id:
            return None
        return self.db.get(User, user_id)
