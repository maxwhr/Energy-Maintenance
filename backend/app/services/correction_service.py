from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ModelOutputCorrection, User
from app.repositories.correction_repository import CorrectionRepository
from app.schemas.correction import CorrectionCreateRequest, CorrectionRead, CorrectionResolveRequest


class CorrectionServiceError(ValueError):
    pass


class CorrectionPermissionError(PermissionError):
    pass


class CorrectionService:
    SUBMIT_ROLES = {"admin", "expert", "engineer"}
    REVIEW_ROLES = {"admin", "expert"}

    def __init__(self, db: Session):
        self.db = db
        self.repository = CorrectionRepository(db)

    def create_correction(self, payload: CorrectionCreateRequest, *, current_user: User) -> dict:
        if current_user.role not in self.SUBMIT_ROLES:
            raise CorrectionPermissionError("Permission denied")
        source_exists = self.repository.source_exists(
            source_type=payload.source_type,
            source_trace_id=payload.source_trace_id,
        )
        if source_exists is False:
            raise CorrectionServiceError("source_trace_id not found")

        metadata = {
            "correction_type": payload.correction_type,
            "source_validation": "verified" if source_exists else "not_verified",
        }
        correction = ModelOutputCorrection(
            source_type=payload.source_type,
            source_trace_id=payload.source_trace_id,
            original_output=self._as_object(payload.original_output),
            corrected_output=self._as_object(payload.corrected_output),
            correction_reason=payload.reason,
            submitted_by=current_user.id,
            review_status="pending_review",
            metadata_json=metadata,
        )
        try:
            correction = self.repository.create(correction)
            self.db.commit()
            self.db.refresh(correction)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise CorrectionServiceError(f"Correction create failed: {exc}") from exc
        return self._read(correction).model_dump(mode="json")

    def list_corrections(
        self,
        *,
        source_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        corrections, total = self.repository.list_corrections(
            source_type=self._clean(source_type),
            status=self._clean(status),
            keyword=self._clean(keyword),
            visible_user=current_user,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._read(correction).model_dump(mode="json") for correction in corrections],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_correction(self, correction_id: UUID, *, current_user: User) -> dict:
        correction = self.repository.get(correction_id)
        if not correction or not self._can_view(correction, current_user):
            raise CorrectionServiceError("Correction not found")
        return self._read(correction).model_dump(mode="json")

    def resolve_correction(
        self,
        correction_id: UUID,
        *,
        payload: CorrectionResolveRequest,
        current_user: User,
    ) -> dict:
        if current_user.role not in self.REVIEW_ROLES:
            raise CorrectionPermissionError("Permission denied")
        correction = self.repository.get(correction_id)
        if not correction:
            raise CorrectionServiceError("Correction not found")
        target_status = "accepted" if payload.action == "accept" else "rejected"
        try:
            correction = self.repository.resolve(
                correction=correction,
                status=target_status,
                reviewer=current_user,
                comment=payload.review_comment,
            )
            self.db.commit()
            self.db.refresh(correction)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise CorrectionServiceError(f"Correction resolve failed: {exc}") from exc
        return self._read(correction).model_dump(mode="json")

    def _read(self, correction: ModelOutputCorrection) -> CorrectionRead:
        submitted_by = self.repository.get_user(correction.submitted_by)
        approved_by = self.repository.get_user(correction.approved_by)
        return CorrectionRead(
            id=correction.id,
            source_type=correction.source_type,
            source_trace_id=correction.source_trace_id,
            original_output=correction.original_output,
            corrected_output=correction.corrected_output,
            correction_reason=correction.correction_reason,
            submitted_by=correction.submitted_by,
            submitted_by_name=self._user_name(submitted_by),
            review_status=correction.review_status,
            approved_by=correction.approved_by,
            approved_by_name=self._user_name(approved_by),
            approved_at=correction.approved_at,
            converted_contribution_id=correction.converted_contribution_id,
            metadata_json=correction.metadata_json,
            created_at=correction.created_at,
            updated_at=correction.updated_at,
        )

    @staticmethod
    def _as_object(value: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        return {"text": value}

    @staticmethod
    def _can_view(correction: ModelOutputCorrection, current_user: User) -> bool:
        if current_user.role in {"admin", "expert"}:
            return True
        if current_user.role == "engineer":
            return correction.submitted_by == current_user.id or correction.review_status in {"accepted", "rejected"}
        return correction.review_status in {"accepted", "rejected"}

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise CorrectionServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise CorrectionServiceError("page_size must be between 1 and 100")

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
