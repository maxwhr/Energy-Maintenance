from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import ModelCallLog


class ModelCallLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, log: ModelCallLog) -> ModelCallLog:
        self.db.add(log)
        self.db.flush()
        return log

    def get_by_id(self, log_id: UUID) -> ModelCallLog | None:
        return self.db.get(ModelCallLog, log_id)

    def get_latest_by_provider(self, provider: str) -> ModelCallLog | None:
        return self.db.scalar(
            select(ModelCallLog)
            .where(ModelCallLog.provider == provider)
            .order_by(ModelCallLog.created_at.desc())
            .limit(1)
        )

    def list(
        self,
        *,
        provider: str | None = None,
        model_name: str | None = None,
        call_type: str | None = None,
        success: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelCallLog], int]:
        filters = []
        if provider:
            filters.append(ModelCallLog.provider == provider)
        if model_name:
            filters.append(ModelCallLog.model_name == model_name)
        if call_type:
            filters.append(ModelCallLog.call_type == call_type)
        if success is not None:
            filters.append(ModelCallLog.success == success)
        if keyword:
            like_keyword = f"%{keyword.strip()}%"
            filters.append(
                or_(
                    ModelCallLog.trace_id.ilike(like_keyword),
                    ModelCallLog.prompt.ilike(like_keyword),
                    ModelCallLog.response.ilike(like_keyword),
                    ModelCallLog.error_message.ilike(like_keyword),
                )
            )

        count_statement = select(func.count()).select_from(ModelCallLog)
        statement = select(ModelCallLog)
        if filters:
            count_statement = count_statement.where(*filters)
            statement = statement.where(*filters)
        total = self.db.scalar(count_statement) or 0
        items = list(
            self.db.scalars(
                statement.order_by(ModelCallLog.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total
