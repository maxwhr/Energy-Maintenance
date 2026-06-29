from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import QARecord


class QARecordRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_qa_record(self, record: QARecord) -> QARecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def list_qa_records(
        self,
        *,
        device_id: UUID | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[QARecord], int]:
        filters = []
        if device_id:
            filters.append(QARecord.device_id == device_id)
        if manufacturer:
            filters.append(QARecord.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(QARecord.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    QARecord.trace_id.ilike(pattern),
                    QARecord.question.ilike(pattern),
                    QARecord.normalized_query.ilike(pattern),
                    QARecord.answer.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(QARecord)
        list_statement = select(QARecord).order_by(QARecord.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        records = list(
            self.db.scalars(
                list_statement
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return records, total

    def get_by_trace_id(self, trace_id: str) -> QARecord | None:
        statement = select(QARecord).where(QARecord.trace_id == trace_id)
        return self.db.scalar(statement)
