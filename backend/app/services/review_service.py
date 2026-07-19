from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument, OperationLog, User
from app.repositories.review_repository import ReviewRepository
from app.schemas.knowledge import KnowledgeChunkRead
from app.schemas.review import KnowledgeReviewDocumentItem, KnowledgeReviewRecordRead
from app.services.candidate_hydration_service import CandidateHydrationService
from app.services.retrieval_scope_service import RetrievalScopeService


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
        equipment_category: str | None = None,
        quality_status: str | None = None,
        document_type: str | None = None,
        keyword: str | None = None,
        normalized_language: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        documents, total = self.repository.list_documents(
            review_status=self._clean(review_status),
            manufacturer=self._clean(manufacturer),
            product_series=self._clean(product_series),
            equipment_category=self._clean(equipment_category),
            quality_status=self._clean(quality_status),
            document_type=self._clean(document_type),
            keyword=self._clean(keyword),
            normalized_language=self._clean(normalized_language),
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
        document = self.repository.get_document(document_id)
        if document:
            metadata = self._approval_metadata(document, reviewer)
            if self._is_vendor_official(document):
                self._validate_vendor_official(document)
                metadata.update(
                    approved_for_pilot=True,
                    approved_for_pilot_by=str(reviewer.id),
                    approved_for_pilot_at=datetime.now(timezone.utc).isoformat(),
                    vendor_review_status="approved_for_pilot",
                )
            document.metadata_json = metadata
        return self._review_document(
            document_id=document_id,
            action="approve",
            after_status="approved",
            reviewer=reviewer,
            comment=comment,
        )

    @staticmethod
    def _approval_metadata(document: KnowledgeDocument, reviewer: User) -> dict:
        metadata = dict(document.metadata_json or {})
        if document.source_type in RetrievalScopeService.REVIEWED_CONTRIBUTION_SOURCE_TYPES:
            now = datetime.now(timezone.utc).isoformat()
            metadata.update(
                human_expert_approved=True,
                competition_approved=True,
                approval_mode="human_expert_approval",
                human_expert_approved_by=str(reviewer.id),
                human_expert_approved_at=now,
            )
        return metadata

    def batch_approve_vendor_official(self, document_ids: list[UUID], *, comment: str | None, reviewer: User) -> dict:
        if reviewer.role not in self.REVIEWER_ROLES:
            raise ReviewPermissionError("Permission denied")
        documents = [self.repository.get_document(item) for item in document_ids]
        if any(item is None for item in documents):
            raise ReviewServiceError("One or more knowledge documents were not found")
        typed = [item for item in documents if item is not None]
        if any(not self._is_vendor_official(item) for item in typed):
            raise ReviewServiceError("Batch approval only supports VENDOR_OFFICIAL documents")
        sources = {(item.metadata_json or {}).get("issuer") for item in typed}
        families = {(item.metadata_json or {}).get("product_family") for item in typed}
        if len(sources) != 1 or len(families) != 1:
            raise ReviewServiceError("Batch documents must have the same issuer and product family")
        for item in typed:
            self._validate_vendor_official(item, batch=True)
        results = []
        for item in typed:
            results.append(self.approve_document(item.id, comment=comment, reviewer=reviewer))
        return {"approved": len(results), "document_ids": [str(item.id) for item in typed], "automatic_approval": False}

    def flag_vendor_official(self, document_id: UUID, *, action: str, comment: str | None, reviewer: User) -> dict:
        if reviewer.role not in self.REVIEWER_ROLES:
            raise ReviewPermissionError("Permission denied")
        document = self.repository.get_document(document_id)
        if not document or not self._is_vendor_official(document):
            raise ReviewServiceError("VENDOR_OFFICIAL document not found")
        mapping = {
            "needs_metadata": ("NEEDS_METADATA", "needs_revision"),
            "marketing_only": ("MARKETING_ONLY", "rejected"),
            "needs_ocr": ("NEEDS_OCR", "needs_revision"),
        }
        if action not in mapping:
            raise ReviewServiceError("Unsupported vendor review flag")
        quality_status, after_status = mapping[action]
        metadata = dict(document.metadata_json or {})
        metadata.update(
            quality_status=quality_status,
            marketing_only=action == "marketing_only",
            ocr_required=action == "needs_ocr",
            approved_for_pilot=False,
            vendor_review_status=action,
        )
        document.metadata_json = metadata
        return self._review_document(
            document_id=document_id, action=action, after_status=after_status,
            reviewer=reviewer, comment=comment,
        )

    def withdraw_vendor_official_approval(
        self,
        document_id: UUID,
        *,
        target_status: str,
        reason: str,
        reviewer: User,
    ) -> dict:
        if reviewer.role not in self.REVIEWER_ROLES:
            raise ReviewPermissionError("Permission denied")
        document = self.repository.get_document(document_id)
        if not document or not self._is_vendor_official(document):
            raise ReviewServiceError("VENDOR_OFFICIAL document not found")
        if document.review_status != "approved":
            raise ReviewServiceError("Only approved documents can be withdrawn")
        if target_status not in {"pending_review", "needs_revision"}:
            raise ReviewServiceError("Unsupported withdrawal target status")
        cleaned_reason = self._clean(reason)
        if not cleaned_reason or len(cleaned_reason) < 10:
            raise ReviewServiceError("Withdrawal reason must contain at least 10 characters")
        pilot_index_count = self.repository.count_vector_indexes(document.id, namespace="pilot_r2")
        if pilot_index_count:
            raise ReviewServiceError(
                "Document already has active pilot_r2 vectors; remove them through the audited Pilot rollback workflow first"
            )

        previous_metadata = dict(document.metadata_json or {})
        now = datetime.now(timezone.utc)
        previous_approval = {
            "reviewed_by": str(document.reviewed_by) if document.reviewed_by else None,
            "reviewed_at": document.reviewed_at.isoformat() if document.reviewed_at else None,
            "review_comment": document.review_comment,
            "approved_for_pilot": bool(previous_metadata.get("approved_for_pilot")),
            "approved_for_pilot_by": previous_metadata.get("approved_for_pilot_by"),
            "approved_for_pilot_at": previous_metadata.get("approved_for_pilot_at"),
        }
        previous_metadata.update(
            approved_for_pilot=False,
            vendor_review_status="require_individual_review",
            quality_status="REQUIRE_INDIVIDUAL_REVIEW",
            requires_individual_review=True,
            pilot_index_excluded=True,
            approval_withdrawn_by=str(reviewer.id),
            approval_withdrawn_at=now.isoformat(),
            approval_withdrawal_reason=cleaned_reason,
        )
        document.metadata_json = previous_metadata
        return self._review_document(
            document_id=document_id,
            action="withdraw_approval",
            after_status=target_status,
            reviewer=reviewer,
            comment=cleaned_reason,
            audit_metadata={
                "automatic_operation": False,
                "reason": cleaned_reason,
                "target_status": target_status,
                "previous_approval": previous_approval,
                "pilot_r2_index_count_at_withdrawal": pilot_index_count,
                "requires_individual_review": True,
            },
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
        audit_metadata: dict | None = None,
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
                audit_metadata=audit_metadata,
            )
            self.db.add(OperationLog(
                module="knowledge_review", action=action, target_type="knowledge_document",
                target_id=str(document.id), operator=reviewer.username,
                trace_id=f"review-{str(review_record.id).replace('-', '')[:24]}",
                detail={
                    "before_status": review_record.before_status, "after_status": review_record.after_status,
                    "source_type": document.source_type,
                    "approved_for_pilot": bool((document.metadata_json or {}).get("approved_for_pilot")),
                    "automatic_approval": False,
                    "automatic_operation": False,
                    "reason": review_record.review_comment,
                    "reviewer_id": str(reviewer.id),
                    "review_record_id": str(review_record.id),
                    **(audit_metadata or {}),
                },
            ))
            self.db.commit()
            CandidateHydrationService.invalidate_scope_cache()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise ReviewServiceError(f"Review update failed: {exc}") from exc
        return {
            "document": self._document_item(document).model_dump(mode="json"),
            "review_record": KnowledgeReviewRecordRead.model_validate(review_record).model_dump(mode="json"),
        }

    @staticmethod
    def _validate_vendor_official(document: KnowledgeDocument, *, batch: bool = False) -> None:
        metadata = document.metadata_json or {}
        if "smartlogger" in document.title.lower() and document.chunk_count >= 100:
            raise ReviewServiceError("SmartLogger long documents require rechunk validation and are excluded from Pilot")
        if not metadata.get("vendor_source_verified"):
            raise ReviewServiceError("Vendor official source has not been verified")
        if not metadata.get("content_parse_verified") or document.parse_status != "parsed":
            raise ReviewServiceError("Vendor document parse quality has not been verified")
        allowed_quality = {"READY_FOR_HUMAN_REVIEW"} if batch else {"READY_FOR_HUMAN_REVIEW", "READY_FOR_DRAFT_IMPORT"}
        if metadata.get("quality_status") not in allowed_quality:
            raise ReviewServiceError("Vendor document quality is not eligible for Pilot approval")
        if metadata.get("marketing_only") or metadata.get("duplicate") or metadata.get("ocr_required"):
            raise ReviewServiceError("Marketing, duplicate, or OCR-required documents cannot be approved for Pilot")

    @staticmethod
    def _is_vendor_official(document: KnowledgeDocument) -> bool:
        metadata = document.metadata_json or {}
        return document.source_type in {"vendor_official", "vendor_official_html"} or metadata.get("source_provenance") == "VENDOR_OFFICIAL"

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
            page_count=document.page_count,
            source_type=document.source_type,
            metadata_json=document.metadata_json,
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
