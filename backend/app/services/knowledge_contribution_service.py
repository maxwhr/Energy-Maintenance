from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeChunk, KnowledgeContribution, KnowledgeDocument, KnowledgeReviewRecord, User
from app.repositories.knowledge_contribution_repository import KnowledgeContributionRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.review import KnowledgeContributionCreate, KnowledgeContributionUpdate
from app.services.document_parser import ParsedDocument, ParsedPage
from app.services.knowledge_service import (
    ALLOWED_DEVICE_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_MANUFACTURERS,
    ALLOWED_PRODUCT_SERIES,
)
from app.services.text_splitter import TextSplitter


class KnowledgeContributionServiceError(ValueError):
    pass


class KnowledgeContributionPermissionError(PermissionError):
    pass


PUBLIC_REVIEW_STATUSES = {"approved", "converted"}
SUBMITTED_STATUSES = {"submitted", "pending_review"}
EDITABLE_BY_OWNER_STATUSES = {"draft", "changes_requested", "rejected"}
REVIEWER_ROLES = {"admin", "expert"}
AUTHOR_ROLES = {"admin", "expert", "engineer"}


class KnowledgeContributionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeContributionRepository(db)
        self.knowledge_repository = KnowledgeRepository(db)
        settings = get_settings()
        self.splitter = TextSplitter(
            chunk_size=settings.DEFAULT_CHUNK_SIZE,
            overlap=settings.DEFAULT_CHUNK_OVERLAP,
        )

    def list_contributions(
        self,
        *,
        current_user: User,
        review_status: str | None = None,
        contribution_type: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_id: UUID | None = None,
        submitted_by: UUID | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        visible_statuses: set[str] | None = None
        owner_or_public_user_id: UUID | None = None
        if current_user.role == "viewer":
            visible_statuses = PUBLIC_REVIEW_STATUSES
        elif current_user.role == "engineer":
            visible_statuses = PUBLIC_REVIEW_STATUSES
            owner_or_public_user_id = current_user.id

        filters = self.repository.build_filters(
            review_status=review_status,
            contribution_type=contribution_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_id=device_id,
            submitted_by=submitted_by,
            keyword=self._clean(keyword),
            visible_statuses=visible_statuses,
            owner_or_public_user_id=owner_or_public_user_id,
        )
        contributions, total = self.repository.list(filters=filters, page=page, page_size=page_size)
        return {
            "items": [self._serialize(contribution) for contribution in contributions],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_contribution(self, contribution_id: UUID, *, current_user: User) -> dict[str, Any]:
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        payload = self._serialize(contribution, include_detail=True)
        payload["review_records"] = [
            self._serialize_review_record(record)
            for record in self.repository.list_review_records(contribution.id)
        ]
        return payload

    def create_contribution(self, payload: KnowledgeContributionCreate, *, current_user: User) -> dict[str, Any]:
        self._require_author(current_user)
        values = payload.model_dump(exclude_unset=True)
        self._validate_domain(values)
        metadata = self._metadata_from_values(values)
        content = self._content_from_values(values, metadata)
        if not content.strip():
            raise KnowledgeContributionServiceError("Contribution content must not be empty")

        contribution = KnowledgeContribution(
            title=values["title"].strip(),
            content=content,
            contribution_type=values.get("contribution_type") or "maintenance_experience",
            manufacturer=values.get("manufacturer"),
            product_series=values.get("product_series"),
            device_type=values.get("device_type") or "pv_inverter",
            device_id=values.get("device_id"),
            source_type="field_contribution",
            source_trace_id=values.get("source_trace_id")
            or values.get("related_diagnosis_trace_id")
            or values.get("qa_trace_id"),
            submitted_by=current_user.id,
            review_status="draft",
            review_comment=None,
            metadata_json=metadata,
        )
        try:
            contribution = self.repository.create(contribution)
            self._record_action(
                contribution=contribution,
                reviewer=current_user,
                action="create",
                comment="Created contribution draft",
                before_status=None,
                after_status=contribution.review_status,
            )
            self.db.commit()
            self.db.refresh(contribution)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeContributionServiceError(f"Contribution create failed: {exc}") from exc
        return self._serialize(contribution, include_detail=True)

    def update_contribution(
        self,
        contribution_id: UUID,
        payload: KnowledgeContributionUpdate,
        *,
        current_user: User,
    ) -> dict[str, Any]:
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        self._ensure_can_edit(contribution, current_user)

        values = payload.model_dump(exclude_unset=True)
        self._validate_domain(values, partial=True)
        metadata = dict(contribution.metadata_json or {})
        metadata.update(self._metadata_from_values(values, base=metadata))

        if "title" in values and values["title"] is not None:
            contribution.title = values["title"].strip()
        if "contribution_type" in values and values["contribution_type"] is not None:
            contribution.contribution_type = values["contribution_type"]
        for field in ("manufacturer", "product_series", "device_type", "device_id"):
            if field in values:
                setattr(contribution, field, values[field])
        if "source_trace_id" in values:
            contribution.source_trace_id = values["source_trace_id"]
        if "content" in values and values["content"] is not None:
            contribution.content = values["content"].strip()
        elif any(field in values for field in STRUCTURED_METADATA_FIELDS):
            contribution.content = self._content_from_values({"title": contribution.title}, metadata)
        contribution.metadata_json = metadata
        contribution.review_comment = None

        try:
            contribution = self.repository.update(contribution)
            self._record_action(
                contribution=contribution,
                reviewer=current_user,
                action="update",
                comment="Updated contribution draft",
                before_status=contribution.review_status,
                after_status=contribution.review_status,
            )
            self.db.commit()
            self.db.refresh(contribution)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeContributionServiceError(f"Contribution update failed: {exc}") from exc
        return self._serialize(contribution, include_detail=True)

    def submit_contribution(self, contribution_id: UUID, *, current_user: User) -> dict[str, Any]:
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        if contribution.submitted_by != current_user.id and current_user.role not in REVIEWER_ROLES:
            raise KnowledgeContributionPermissionError("Only the author or reviewer can submit this contribution")
        if contribution.review_status not in {"draft", "changes_requested", "rejected"}:
            raise KnowledgeContributionServiceError("Only draft, changes_requested, or rejected contributions can be submitted")
        return self._transition(
            contribution,
            reviewer=current_user,
            action="submit",
            after_status="submitted",
            comment="Submitted for expert review",
        )

    def request_changes(self, contribution_id: UUID, *, current_user: User, comment: str | None) -> dict[str, Any]:
        self._require_reviewer(current_user)
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        self._ensure_reviewable(contribution)
        return self._transition(
            contribution,
            reviewer=current_user,
            action="request_changes",
            after_status="changes_requested",
            comment=comment or "Reviewer requested changes",
        )

    def approve(self, contribution_id: UUID, *, current_user: User, comment: str | None) -> dict[str, Any]:
        self._require_reviewer(current_user)
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        self._ensure_reviewable(contribution)
        return self._transition(
            contribution,
            reviewer=current_user,
            action="approve",
            after_status="approved",
            comment=comment or "Approved by reviewer",
        )

    def reject(self, contribution_id: UUID, *, current_user: User, comment: str | None) -> dict[str, Any]:
        self._require_reviewer(current_user)
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        self._ensure_reviewable(contribution)
        return self._transition(
            contribution,
            reviewer=current_user,
            action="reject",
            after_status="rejected",
            comment=comment or "Rejected by reviewer",
        )

    def archive(self, contribution_id: UUID, *, current_user: User, comment: str | None) -> dict[str, Any]:
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        if current_user.role not in REVIEWER_ROLES and contribution.submitted_by != current_user.id:
            raise KnowledgeContributionPermissionError("Only author or reviewer can archive this contribution")
        if contribution.review_status in {"converted", "archived"}:
            raise KnowledgeContributionServiceError("Converted or archived contributions cannot be archived again")
        return self._transition(
            contribution,
            reviewer=current_user,
            action="archive",
            after_status="archived",
            comment=comment or "Archived contribution",
        )

    def convert_to_document(self, contribution_id: UUID, *, current_user: User, comment: str | None) -> dict[str, Any]:
        self._require_reviewer(current_user)
        contribution = self._get_allowed(contribution_id, current_user=current_user)
        if contribution.review_status != "approved":
            raise KnowledgeContributionServiceError("Only approved contributions can be converted to knowledge documents")
        if contribution.approved_document_id:
            raise KnowledgeContributionServiceError("Contribution has already been converted")

        metadata = dict(contribution.metadata_json or {})
        now = datetime.now(timezone.utc)
        document = KnowledgeDocument(
            title=f"一线经验：{contribution.title}",
            manufacturer=contribution.manufacturer or "huawei",
            product_series=contribution.product_series,
            device_type=contribution.device_type or "pv_inverter",
            document_type=self._document_type_for_contribution(contribution.contribution_type),
            source=f"knowledge_contribution:{contribution.id}",
            source_type="knowledge_contribution",
            parse_status="parsed",
            parser_name="field_contribution",
            chunk_count=0,
            summary=self._summary_from_contribution(contribution),
            metadata_json={
                "contribution_id": str(contribution.id),
                "source_type": "field_contribution",
                "media_ids": metadata.get("media_ids", []),
                "fault_type": metadata.get("fault_type"),
                "alarm_code": metadata.get("alarm_code"),
            },
            review_status="approved",
            submitted_by=contribution.submitted_by,
            reviewed_by=current_user.id,
            reviewed_at=now,
            review_comment=comment,
            status="active",
        )

        parsed_document = ParsedDocument(
            text=contribution.content,
            pages=[ParsedPage(page_number=None, text=contribution.content)],
            page_count=None,
            metadata={"parser": "field_contribution", "contribution_id": str(contribution.id)},
            warnings=[],
        )
        chunks = self.splitter.split(parsed_document)
        if not chunks:
            raise KnowledgeContributionServiceError("Converted contribution generated no knowledge chunks")

        try:
            document = self.knowledge_repository.create_document(document)
            chunk_models = [
                KnowledgeChunk(
                    document_id=document.id,
                    manufacturer=document.manufacturer,
                    product_series=document.product_series,
                    device_type=document.device_type,
                    document_type=document.document_type,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    section_title=chunk.section_title or "一线经验",
                    char_count=chunk.char_count,
                    page_number=chunk.page_number,
                    embedding_status="pending",
                    metadata_json={
                        **chunk.metadata,
                        "contribution_id": str(contribution.id),
                        "source_type": "field_contribution",
                    },
                    status="active",
                )
                for chunk in chunks
            ]
            self.knowledge_repository.create_chunks(chunk_models)
            document.chunk_count = len(chunk_models)
            document.parsed_at = now
            self.knowledge_repository.update_document(document)

            before_status = contribution.review_status
            contribution.review_status = "converted"
            contribution.approved_document_id = document.id
            contribution.review_comment = comment or "Converted to approved knowledge document"
            contribution.metadata_json = {
                **metadata,
                "converted_document_id": str(document.id),
                "converted_at": now.isoformat(),
            }
            self.repository.update(contribution)
            self._record_action(
                contribution=contribution,
                reviewer=current_user,
                action="convert_to_document",
                comment=contribution.review_comment,
                before_status=before_status,
                after_status=contribution.review_status,
                document_id=document.id,
            )
            self.db.commit()
            self.db.refresh(contribution)
            self.db.refresh(document)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeContributionServiceError(f"Contribution conversion failed: {exc}") from exc

        return {
            "contribution": self._serialize(contribution, include_detail=True),
            "document": {
                "id": str(document.id),
                "title": document.title,
                "document_type": document.document_type,
                "manufacturer": document.manufacturer,
                "product_series": document.product_series,
                "device_type": document.device_type,
                "parse_status": document.parse_status,
                "review_status": document.review_status,
                "chunk_count": document.chunk_count,
                "source": document.source,
                "status": document.status,
            },
            "chunk_count": document.chunk_count,
        }

    def _transition(
        self,
        contribution: KnowledgeContribution,
        *,
        reviewer: User,
        action: str,
        after_status: str,
        comment: str | None,
    ) -> dict[str, Any]:
        before_status = contribution.review_status
        contribution.review_status = after_status
        contribution.review_comment = comment
        try:
            contribution = self.repository.update(contribution)
            self._record_action(
                contribution=contribution,
                reviewer=reviewer,
                action=action,
                comment=comment,
                before_status=before_status,
                after_status=after_status,
            )
            self.db.commit()
            self.db.refresh(contribution)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise KnowledgeContributionServiceError(f"Contribution state transition failed: {exc}") from exc
        return self._serialize(contribution, include_detail=True)

    def _record_action(
        self,
        *,
        contribution: KnowledgeContribution,
        reviewer: User,
        action: str,
        comment: str | None,
        before_status: str | None,
        after_status: str | None,
        document_id: UUID | None = None,
    ) -> None:
        self.repository.add_review_record(
            KnowledgeReviewRecord(
                contribution_id=contribution.id,
                document_id=document_id,
                reviewer_id=reviewer.id,
                review_action=action,
                review_comment=comment,
                before_status=before_status,
                after_status=after_status,
                reviewed_at=datetime.now(timezone.utc),
                metadata_json={"source": "knowledge_contribution_workflow"},
            )
        )

    def _get_allowed(self, contribution_id: UUID, *, current_user: User) -> KnowledgeContribution:
        contribution = self.repository.get_by_id(contribution_id)
        if not contribution:
            raise KnowledgeContributionServiceError("Knowledge contribution not found")
        if current_user.role in REVIEWER_ROLES:
            return contribution
        if current_user.role == "viewer" and contribution.review_status in PUBLIC_REVIEW_STATUSES:
            return contribution
        if current_user.role == "engineer" and (
            contribution.submitted_by == current_user.id or contribution.review_status in PUBLIC_REVIEW_STATUSES
        ):
            return contribution
        raise KnowledgeContributionPermissionError("Permission denied")

    @staticmethod
    def _require_author(current_user: User) -> None:
        if current_user.role not in AUTHOR_ROLES:
            raise KnowledgeContributionPermissionError("Only engineers, experts, and admins can create contributions")

    @staticmethod
    def _require_reviewer(current_user: User) -> None:
        if current_user.role not in REVIEWER_ROLES:
            raise KnowledgeContributionPermissionError("Only experts and admins can review contributions")

    @staticmethod
    def _ensure_reviewable(contribution: KnowledgeContribution) -> None:
        if contribution.review_status not in SUBMITTED_STATUSES:
            raise KnowledgeContributionServiceError("Only submitted contributions can be reviewed")

    @staticmethod
    def _ensure_can_edit(contribution: KnowledgeContribution, current_user: User) -> None:
        if current_user.role in REVIEWER_ROLES and contribution.review_status != "converted":
            return
        if contribution.submitted_by == current_user.id and contribution.review_status in EDITABLE_BY_OWNER_STATUSES:
            return
        raise KnowledgeContributionPermissionError("This contribution cannot be edited in its current state")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise KnowledgeContributionServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise KnowledgeContributionServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _validate_domain(values: dict[str, Any], *, partial: bool = False) -> None:
        manufacturer = values.get("manufacturer")
        product_series = values.get("product_series")
        device_type = values.get("device_type")
        document_type = values.get("document_type")
        if manufacturer and manufacturer not in ALLOWED_MANUFACTURERS:
            raise KnowledgeContributionServiceError("manufacturer must be huawei or sungrow")
        if product_series and product_series not in ALLOWED_PRODUCT_SERIES:
            raise KnowledgeContributionServiceError("product_series must be SUN2000, FusionSolar, or SG")
        if device_type and device_type not in ALLOWED_DEVICE_TYPES:
            raise KnowledgeContributionServiceError("device_type must be pv_inverter")
        if document_type and document_type not in ALLOWED_DOCUMENT_TYPES:
            raise KnowledgeContributionServiceError("document_type is not supported")
        if not partial:
            title = values.get("title")
            if not isinstance(title, str) or not title.strip():
                raise KnowledgeContributionServiceError("title must not be empty")

    @staticmethod
    def _metadata_from_values(values: dict[str, Any], base: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata = dict(base or {})
        supplied = values.get("metadata_json")
        if isinstance(supplied, dict):
            metadata.update(supplied)
        for field in STRUCTURED_METADATA_FIELDS:
            if field in values:
                metadata[field] = KnowledgeContributionService._json_safe(values[field])
        metadata["source_type"] = "field_contribution"
        return metadata

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, list):
            return [KnowledgeContributionService._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {key: KnowledgeContributionService._json_safe(item) for key, item in value.items()}
        return value

    @staticmethod
    def _content_from_values(values: dict[str, Any], metadata: dict[str, Any]) -> str:
        explicit = values.get("content")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        sections = [
            ("故障现象", metadata.get("symptom_description")),
            ("处理过程", metadata.get("diagnosis_process")),
            ("原因判断", metadata.get("root_cause")),
            ("处理措施", metadata.get("solution")),
            ("安全注意事项", metadata.get("safety_notes")),
            ("使用工具", metadata.get("tools_used")),
            ("更换部件", metadata.get("parts_used")),
        ]
        lines = [f"# {values.get('title', '一线检修经验')}"]
        for heading, value in sections:
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                body = "\n".join(f"- {item}" for item in value if str(item).strip())
            else:
                body = str(value).strip()
            if body:
                lines.append(f"\n## {heading}\n{body}")
        return "\n".join(lines).strip()

    @staticmethod
    def _document_type_for_contribution(contribution_type: str) -> str:
        if contribution_type in {"fault_case", "alarm_experience"}:
            return "fault_case"
        if contribution_type in {"sop_suggestion", "procedure"}:
            return "sop"
        return "maintenance_record"

    @staticmethod
    def _summary_from_contribution(contribution: KnowledgeContribution) -> str:
        text = " ".join(contribution.content.split())
        return text[:240]

    def _serialize(self, contribution: KnowledgeContribution, *, include_detail: bool = False) -> dict[str, Any]:
        metadata = contribution.metadata_json or {}
        approved_document = getattr(contribution, "approved_document", None)
        submitter = getattr(contribution, "submitter", None)
        device = getattr(contribution, "device", None)
        payload = {
            "id": str(contribution.id),
            "title": contribution.title,
            "content": contribution.content,
            "contribution_type": contribution.contribution_type,
            "manufacturer": contribution.manufacturer,
            "product_series": contribution.product_series,
            "device_type": contribution.device_type,
            "device_id": str(contribution.device_id) if contribution.device_id else None,
            "device_name": getattr(device, "device_name", None),
            "source_type": contribution.source_type,
            "source_trace_id": contribution.source_trace_id,
            "submitted_by": str(contribution.submitted_by) if contribution.submitted_by else None,
            "submitted_by_name": getattr(submitter, "display_name", None) or getattr(submitter, "username", None),
            "review_status": contribution.review_status,
            "review_comment": contribution.review_comment,
            "approved_document_id": str(contribution.approved_document_id) if contribution.approved_document_id else None,
            "approved_document_title": getattr(approved_document, "title", None),
            "metadata_json": metadata,
            "created_at": contribution.created_at,
            "updated_at": contribution.updated_at,
        }
        for field in STRUCTURED_METADATA_FIELDS:
            payload[field] = metadata.get(field)
        if not include_detail:
            payload["content_preview"] = " ".join(contribution.content.split())[:180]
        return payload

    @staticmethod
    def _serialize_review_record(record: KnowledgeReviewRecord) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "contribution_id": str(record.contribution_id) if record.contribution_id else None,
            "document_id": str(record.document_id) if record.document_id else None,
            "reviewer_id": str(record.reviewer_id) if record.reviewer_id else None,
            "review_action": record.review_action,
            "review_comment": record.review_comment,
            "before_status": record.before_status,
            "after_status": record.after_status,
            "reviewed_at": record.reviewed_at,
            "metadata_json": record.metadata_json,
            "created_at": record.created_at,
        }

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


STRUCTURED_METADATA_FIELDS = (
    "fault_type",
    "alarm_code",
    "symptom_description",
    "diagnosis_process",
    "root_cause",
    "solution",
    "tools_used",
    "parts_used",
    "safety_notes",
    "media_ids",
    "related_diagnosis_trace_id",
    "related_task_id",
    "qa_trace_id",
)
