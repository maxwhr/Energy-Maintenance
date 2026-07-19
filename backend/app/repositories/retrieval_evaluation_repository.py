from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun


class RetrievalEvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_case(self, item: RetrievalEvaluationCase) -> RetrievalEvaluationCase:
        self.db.add(item)
        self.db.flush()
        return item

    def list_cases(self, *, split: str | None = None, page: int = 1, page_size: int = 100):
        filters = [RetrievalEvaluationCase.dataset_split == split] if split else []
        total = int(self.db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(*filters)) or 0)
        items = list(self.db.scalars(
            select(RetrievalEvaluationCase).where(*filters)
            .order_by(RetrievalEvaluationCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ))
        return items, total

    def evaluation_cases(self, *, split: str, limit: int, dataset_version: str | None = None) -> list[RetrievalEvaluationCase]:
        filters = [
            RetrievalEvaluationCase.dataset_split == split,
            RetrievalEvaluationCase.review_status.in_(["engineering_verified", "expert_verified"]),
        ]
        if dataset_version:
            matching = int(self.db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
                *filters, RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == dataset_version,
            )) or 0)
            if matching:
                filters.append(RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == dataset_version)
        return list(self.db.scalars(
            select(RetrievalEvaluationCase).where(*filters)
            .order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.created_at).limit(limit)
        ))

    def create_run(self, item: RetrievalEvaluationRun) -> RetrievalEvaluationRun:
        self.db.add(item)
        self.db.flush()
        return item

    def add_result(self, item: RetrievalEvaluationResult) -> None:
        self.db.add(item)

    def list_runs(self, *, page: int, page_size: int):
        total = int(self.db.scalar(select(func.count()).select_from(RetrievalEvaluationRun)) or 0)
        items = list(self.db.scalars(
            select(RetrievalEvaluationRun).order_by(RetrievalEvaluationRun.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ))
        return items, total

    def get_run(self, run_id: UUID):
        run = self.db.get(RetrievalEvaluationRun, run_id)
        if not run:
            return None, []
        results = list(self.db.scalars(
            select(RetrievalEvaluationResult).where(RetrievalEvaluationResult.run_id == run_id)
            .order_by(RetrievalEvaluationResult.created_at)
        ))
        return run, results
