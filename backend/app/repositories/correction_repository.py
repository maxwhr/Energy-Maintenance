from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import DiagnosisRecord, MaintenanceTask, ModelOutputCorrection, QARecord, SOPExecutionRecord, User


class CorrectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, correction: ModelOutputCorrection) -> ModelOutputCorrection:
        self.db.add(correction)
        self.db.flush()
        self.db.refresh(correction)
        return correction

    def get(self, correction_id: UUID) -> ModelOutputCorrection | None:
        return self.db.get(ModelOutputCorrection, correction_id)

    def list_corrections(
        self,
        *,
        source_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        visible_user: User | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelOutputCorrection], int]:
        filters = []
        if source_type:
            filters.append(ModelOutputCorrection.source_type == source_type)
        if status:
            filters.append(ModelOutputCorrection.review_status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    ModelOutputCorrection.source_trace_id.ilike(pattern),
                    ModelOutputCorrection.correction_reason.ilike(pattern),
                )
            )
        if visible_user:
            if visible_user.role == "engineer":
                filters.append(
                    or_(
                        ModelOutputCorrection.submitted_by == visible_user.id,
                        ModelOutputCorrection.review_status.in_(["accepted", "rejected"]),
                    )
                )
            elif visible_user.role == "viewer":
                filters.append(ModelOutputCorrection.review_status.in_(["accepted", "rejected"]))

        count_statement = select(func.count()).select_from(ModelOutputCorrection)
        list_statement = select(ModelOutputCorrection).order_by(ModelOutputCorrection.updated_at.desc(), ModelOutputCorrection.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        corrections = list(self.db.scalars(list_statement.offset((page - 1) * page_size).limit(page_size)))
        return corrections, total

    def resolve(
        self,
        *,
        correction: ModelOutputCorrection,
        status: str,
        reviewer: User,
        comment: str | None,
    ) -> ModelOutputCorrection:
        correction.review_status = status
        correction.approved_by = reviewer.id
        correction.approved_at = datetime.now(timezone.utc)
        metadata = dict(correction.metadata_json or {})
        metadata["review_comment"] = comment
        correction.metadata_json = metadata
        self.db.add(correction)
        self.db.flush()
        self.db.refresh(correction)
        return correction

    def source_exists(self, *, source_type: str, source_trace_id: str) -> bool | None:
        if source_type == "qa":
            return bool(self.db.scalar(select(QARecord.id).where(QARecord.trace_id == source_trace_id)))
        if source_type == "diagnosis":
            return bool(self.db.scalar(select(DiagnosisRecord.id).where(DiagnosisRecord.trace_id == source_trace_id)))
        if source_type == "task":
            try:
                task_id = UUID(source_trace_id)
            except ValueError:
                return None
            return bool(self.db.scalar(select(MaintenanceTask.id).where(MaintenanceTask.id == task_id)))
        if source_type == "sop":
            try:
                execution_id = UUID(source_trace_id)
            except ValueError:
                return None
            return bool(self.db.scalar(select(SOPExecutionRecord.id).where(SOPExecutionRecord.id == execution_id)))
        return None

    def get_user(self, user_id: UUID | None) -> User | None:
        if not user_id:
            return None
        return self.db.get(User, user_id)
