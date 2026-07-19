from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    OperationLog,
    RetrievalDatasetFreeze,
    RetrievalEvaluationCase,
    RetrievalOfficialRunLock,
    VectorIndexRun,
)


class RetrievalPilotRepository:
    SOURCE_TYPE = "task25b_r2_formal_pilot"

    def __init__(self, db: Session):
        self.db = db

    def list_cases(
        self,
        *,
        category: str | None,
        difficulty: str | None,
        review_status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[RetrievalEvaluationCase], int]:
        filters = [RetrievalEvaluationCase.source_type == self.SOURCE_TYPE]
        if category:
            filters.append(RetrievalEvaluationCase.category == category)
        if difficulty:
            filters.append(RetrievalEvaluationCase.difficulty == difficulty)
        if review_status:
            filters.append(RetrievalEvaluationCase.review_status == review_status)
        total = int(self.db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(*filters)) or 0)
        items = list(
            self.db.scalars(
                select(RetrievalEvaluationCase)
                .where(*filters)
                .order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.created_at)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def all_cases(self) -> list[RetrievalEvaluationCase]:
        return list(
            self.db.scalars(
                select(RetrievalEvaluationCase)
                .where(RetrievalEvaluationCase.source_type == self.SOURCE_TYPE)
                .order_by(RetrievalEvaluationCase.id)
            )
        )

    def get_case(self, case_id: UUID) -> RetrievalEvaluationCase | None:
        item = self.db.get(RetrievalEvaluationCase, case_id)
        return item if item and item.source_type == self.SOURCE_TYPE else None

    def get_freeze(self, dataset_version: str) -> RetrievalDatasetFreeze | None:
        return self.db.scalar(
            select(RetrievalDatasetFreeze).where(RetrievalDatasetFreeze.dataset_version == dataset_version)
        )

    def list_freezes(self) -> list[RetrievalDatasetFreeze]:
        return list(self.db.scalars(select(RetrievalDatasetFreeze).order_by(RetrievalDatasetFreeze.created_at.desc())))

    def get_run_lock(self, freeze_id: UUID, purpose: str) -> RetrievalOfficialRunLock | None:
        return self.db.scalar(
            select(RetrievalOfficialRunLock).where(
                RetrievalOfficialRunLock.dataset_freeze_id == freeze_id,
                RetrievalOfficialRunLock.run_purpose == purpose,
            )
        )

    def get_session(self, session_id: UUID) -> VectorIndexRun | None:
        item = self.db.get(VectorIndexRun, session_id)
        return item if item and item.run_type == "task25b_r2_pilot_session" else None

    def active_sessions(self) -> list[VectorIndexRun]:
        return list(
            self.db.scalars(
                select(VectorIndexRun).where(
                    VectorIndexRun.run_type == "task25b_r2_pilot_session",
                    VectorIndexRun.status == "running",
                ).order_by(VectorIndexRun.created_at.desc())
            )
        )

    def audit(self, *, action: str, target_type: str, target_id: str, operator: str, trace_id: str, detail: dict) -> None:
        self.db.add(
            OperationLog(
                module="retrieval_pilot",
                action=action,
                target_type=target_type,
                target_id=target_id,
                operator=operator,
                trace_id=trace_id,
                detail=detail,
            )
        )
