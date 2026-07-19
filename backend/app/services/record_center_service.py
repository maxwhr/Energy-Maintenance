from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.record_center_repository import RecordCenterRepository


class RecordCenterServiceError(ValueError):
    pass


class RecordCenterService:
    ALLOWED_RECORD_TYPES = {
        "all",
        "qa",
        "diagnosis",
        "task",
        "maintenance_record",
        "sop_execution",
        "knowledge_document",
        "knowledge_contribution",
        "media",
        "knowledge_graph_node",
        "knowledge_graph_edge",
        "knowledge_graph_extraction_run",
    }

    def __init__(self, db: Session):
        self.repository = RecordCenterRepository(db)

    def overview(self) -> dict:
        return self.repository.overview()

    def search(
        self,
        *,
        record_type: str = "all",
        device_id: UUID | None = None,
        workflow_id: str | None = None,
        actor_id: UUID | None = None,
        keyword: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort_direction: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_record_type(record_type, allow_all=True)
        self._validate_page(page, page_size)
        if sort_direction not in {"asc", "desc"}:
            raise RecordCenterServiceError("sort_direction must be asc or desc")
        return self.repository.search(
            record_type=record_type,
            device_id=device_id,
            workflow_id=self._clean(workflow_id),
            actor_id=actor_id,
            keyword=self._clean(keyword),
            trace_id=self._clean(trace_id),
            status=self._clean(status),
            fault_type=self._clean(fault_type),
            alarm_code=self._clean(alarm_code),
            manufacturer=self._clean(manufacturer),
            product_series=self._clean(product_series),
            date_from=self._parse_date(date_from, is_end=False),
            date_to=self._parse_date(date_to, is_end=True),
            sort_direction=sort_direction,
            page=page,
            page_size=page_size,
        )

    def detail(self, *, record_type: str, record_id: UUID) -> dict:
        self._validate_record_type(record_type, allow_all=False)
        detail = self.repository.get_detail(record_type=record_type, record_id=record_id)
        if not detail:
            raise RecordCenterServiceError("Record not found")
        return detail

    def device_timeline(
        self,
        *,
        device_id: UUID,
        date_from: str | None = None,
        date_to: str | None = None,
        record_type: str | None = None,
        limit: int = 50,
    ) -> dict:
        if record_type:
            self._validate_record_type(record_type, allow_all=False)
        if limit < 1 or limit > 200:
            raise RecordCenterServiceError("limit must be between 1 and 200")
        result = self.repository.device_timeline(
            device_id=device_id,
            date_from=self._parse_date(date_from, is_end=False),
            date_to=self._parse_date(date_to, is_end=True),
            record_type=record_type,
            limit=limit,
        )
        if not result:
            raise RecordCenterServiceError("Device not found")
        return result

    def _validate_record_type(self, record_type: str, *, allow_all: bool) -> None:
        if record_type not in self.ALLOWED_RECORD_TYPES:
            raise RecordCenterServiceError("Invalid record_type")
        if record_type == "all" and not allow_all:
            raise RecordCenterServiceError("record_type all is not supported for detail")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise RecordCenterServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise RecordCenterServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _clean(value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @staticmethod
    def _parse_date(value: str | None, *, is_end: bool) -> datetime | None:
        if not value:
            return None
        cleaned = value.strip()
        try:
            if len(cleaned) == 10:
                parsed_date = datetime.fromisoformat(cleaned).date()
                return datetime.combine(parsed_date, time.max if is_end else time.min)
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RecordCenterServiceError("date_from/date_to must be ISO date or datetime") from exc
