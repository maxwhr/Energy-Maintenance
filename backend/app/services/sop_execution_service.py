from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import SOPExecutionRecord, User
from app.repositories.sop_repository import SOPRepository
from app.schemas.sop import (
    ALLOWED_SOP_EXECUTION_STATUSES,
    SOPExecutionRecordCreate,
    SOPExecutionRecordDetail,
    SOPExecutionRecordRead,
    SOPExecutionRecordUpdate,
)


class SOPExecutionServiceError(ValueError):
    pass


class SOPExecutionService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SOPRepository(db)

    def list_executions(
        self,
        *,
        template_id: UUID | None = None,
        task_id: UUID | None = None,
        executor_id: UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        if status:
            self._validate_status(status)
        executions, total = self.repository.list_executions(
            template_id=template_id,
            task_id=task_id,
            executor_id=executor_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._execution_payload(record) for record in executions],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_execution(self, execution_id: UUID, current_user: User) -> dict | None:
        record = self.repository.get_execution(execution_id)
        if not record:
            return None
        self._ensure_read_allowed(record, current_user)
        return self._execution_detail_payload(record)

    def create_execution(self, payload: SOPExecutionRecordCreate, current_user: User) -> dict:
        template = self.repository.get_template(payload.template_id)
        if not template:
            raise SOPExecutionServiceError("SOP template not found")
        if template.status != "active":
            raise SOPExecutionServiceError("SOP execution requires an active template")
        if payload.task_id and not self.repository.get_task(payload.task_id):
            raise SOPExecutionServiceError("Maintenance task not found")
        self._validate_status(payload.status)
        record = SOPExecutionRecord(
            task_id=payload.task_id,
            template_id=template.id,
            executor_id=current_user.id,
            step_results=payload.step_results or self._default_step_results(template.steps or []),
            abnormal_notes=payload.abnormal_notes,
            status=payload.status,
            started_at=payload.started_at,
            completed_at=payload.completed_at,
            metadata_json=payload.metadata_json,
        )
        self._apply_status_timestamps(record)
        try:
            saved = self.repository.create_execution(record)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise SOPExecutionServiceError(f"SOP execution write failed: {exc}") from exc
        return self._execution_payload(saved)

    def update_execution(
        self,
        execution_id: UUID,
        payload: SOPExecutionRecordUpdate,
        current_user: User,
    ) -> dict:
        record = self.repository.get_execution(execution_id)
        if not record:
            raise SOPExecutionServiceError("SOP execution record not found")
        self._ensure_write_allowed(record, current_user)
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"]:
            self._validate_status(data["status"])
            self._validate_transition(record.status, data["status"])
        for field, value in data.items():
            setattr(record, field, value)
        self._apply_status_timestamps(record)
        try:
            saved = self.repository.update_execution(record)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise SOPExecutionServiceError(f"SOP execution update failed: {exc}") from exc
        return self._execution_detail_payload(saved)

    @staticmethod
    def _default_step_results(steps: list[dict]) -> list[dict]:
        results = []
        for index, step in enumerate(steps, start=1):
            step_index = int(step.get("step_index") or index)
            results.append(
                {
                    "step_index": step_index,
                    "step_title": step.get("step_title") or f"Step {step_index}",
                    "checked": False,
                    "note": None,
                    "checked_at": None,
                }
            )
        return results

    @staticmethod
    def _apply_status_timestamps(record: SOPExecutionRecord) -> None:
        now = datetime.now(timezone.utc)
        if record.status == "in_progress" and record.started_at is None:
            record.started_at = now
        if record.status in {"completed", "aborted"} and record.completed_at is None:
            record.completed_at = now
        if record.status in {"completed", "aborted"} and record.started_at is None:
            record.started_at = now

    @staticmethod
    def _validate_transition(current_status: str, next_status: str) -> None:
        if current_status == next_status:
            return
        allowed = {
            "not_started": {"in_progress", "aborted"},
            "in_progress": {"completed", "aborted"},
            "completed": set(),
            "aborted": set(),
        }
        if next_status not in allowed.get(current_status, set()):
            raise SOPExecutionServiceError(f"Invalid SOP execution status transition: {current_status} -> {next_status}")

    @staticmethod
    def _ensure_read_allowed(record: SOPExecutionRecord, current_user: User) -> None:
        if current_user.role in {"admin", "expert", "viewer"}:
            return
        if current_user.role == "engineer" and record.executor_id == current_user.id:
            return
        raise SOPExecutionServiceError("Permission denied for this SOP execution record")

    @staticmethod
    def _ensure_write_allowed(record: SOPExecutionRecord, current_user: User) -> None:
        if current_user.role in {"admin", "expert"}:
            return
        if current_user.role == "engineer" and record.executor_id == current_user.id:
            return
        raise SOPExecutionServiceError("Permission denied for this SOP execution record")

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in ALLOWED_SOP_EXECUTION_STATUSES:
            raise SOPExecutionServiceError("unsupported SOP execution status")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise SOPExecutionServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise SOPExecutionServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _execution_payload(record: SOPExecutionRecord) -> dict:
        return SOPExecutionRecordRead.model_validate(record).model_dump(mode="json")

    @staticmethod
    def _execution_detail_payload(record: SOPExecutionRecord) -> dict:
        return SOPExecutionRecordDetail.model_validate(record).model_dump(mode="json")
