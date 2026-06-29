from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument, User
from app.repositories.review_repository import ReviewRepository
from app.schemas.knowledge import KnowledgeChunkRead
from app.schemas.review import KnowledgeReviewDocumentItem, KnowledgeReviewRecordRead


class ReviewServiceError(ValueError):
    pass


class ReviewPermissionError(PermissionError):
    pass


class ReviewService:
    REVIEWER_ROLES = {"admin", "expert"}

    def __init__(self, db: Session):
        self.db = db
        self.repository = ReviewRepository(db)

    def list_knowledge_documents(
        self,
        *,
        review_status: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        document_type: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        documents, total = self.repository.list_documents(
            review_status=self._clean(review_status),
            manufacturer=self._clean(manufacturer),
            product_series=self._clean(product_series),
            document_type=self._clean(document_type),
            keyword=self._clean(keyword),
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._document_item(document).model_dump(mode="json") for document in documents],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_knowledge_detail(self, document_id: UUID) -> dict:
        document = self.repository.get_document(document_id)
        if not document:
            raise ReviewServiceError("Knowledge document not found")
        chunks = self.repository.list_chunk_preview(document_id)
        review_records = self.repository.list_review_records(document_id)
        return {
            "document": self._document_item(document).model_dump(mode="json"),
            "chunk_preview": [
                KnowledgeChunkRead.model_validate(chunk).model_dump(mode="json")
                for chunk in chunks
            ],
            "review_records": [
                KnowledgeReviewRecordRead.model_validate(record).model_dump(mode="json")
                for record in review_records
            ],
        }

    def approve_document(self, document_id: UUID, *, comment: str | None, reviewer: User) -> dict:
        return self._review_document(
            document_id=document_id,
            action="approve",
            after_status="approved",
            reviewer=reviewer,
            comment=comment,
        )

    def reject_document(self, document_id: UUID, *, comment: str | None, reviewer: User) -> dict:
        return self._review_document(
            document_id=document_id,
            action="reject",
            after_status="rejected",
            reviewer=reviewer,
            comment=comment,
        )

    def archive_document(self, document_id: UUID, *, comment: str | None, reviewer: User) -> dict:
        return self._review_document(
            document_id=document_id,
            action="archive",
            after_status="archived",
            reviewer=reviewer,
            comment=comment,
            archive_status=True,
        )

    def _review_document(
        self,
        *,
        document_id: UUID,
        action: str,
        after_status: str,
        reviewer: User,
        comment: str | None,
        archive_status: bool = False,
    ) -> dict:
        if reviewer.role not in self.REVIEWER_ROLES:
            raise ReviewPermissionError("Permission denied")
        document = self.repository.get_document(document_id)
        if not document:
            raise ReviewServiceError("Knowledge document not found")
        try:
            document, review_record = self.repository.update_document_review(
                document=document,
                action=action,
                after_status=after_status,
                reviewer=reviewer,
                comment=self._clean(comment),
                archive_status=archive_status,
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ReviewServiceError(f"Review update failed: {exc}") from exc
        return {
            "document": self._document_item(document).model_dump(mode="json"),
            "review_record": KnowledgeReviewRecordRead.model_validate(review_record).model_dump(mode="json"),
        }

    def _document_item(self, document: KnowledgeDocument) -> KnowledgeReviewDocumentItem:
        submitted_by = self.repository.get_user(document.submitted_by)
        reviewed_by = self.repository.get_user(document.reviewed_by)
        return KnowledgeReviewDocumentItem(
            id=document.id,
            title=document.title,
            manufacturer=document.manufacturer,
            product_series=document.product_series,
            device_type=document.device_type,
            document_type=document.document_type,
            source=document.source,
            parse_status=document.parse_status,
            review_status=document.review_status,
            status=document.status,
            chunk_count=document.chunk_count,
            reviewed_by=document.reviewed_by,
            reviewed_by_name=self._user_name(reviewed_by),
            reviewed_at=document.reviewed_at,
            review_comment=document.review_comment,
            submitted_by=document.submitted_by,
            submitted_by_name=self._user_name(submitted_by),
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise ReviewServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise ReviewServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _user_name(user: User | None) -> str | None:
        if not user:
            return None
        return user.display_name or user.username
