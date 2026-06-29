from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, DeviceMaintenanceRecord, DiagnosisRecord, UploadedMedia


class DiagnosisRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def get_media(self, media_id: UUID) -> UploadedMedia | None:
        return self.db.get(UploadedMedia, media_id)

    def create_record(self, record: DiagnosisRecord) -> DiagnosisRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def link_media_to_record(self, media_items: list[UploadedMedia], record_id: UUID) -> None:
        for media in media_items:
            media.diagnosis_record_id = record_id
            self.db.add(media)

    def list_records(
        self,
        *,
        device_id: UUID | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DiagnosisRecord], int]:
        filters = []
        if device_id:
            filters.append(DiagnosisRecord.device_id == device_id)
        if manufacturer:
            filters.append(DiagnosisRecord.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(DiagnosisRecord.product_series == product_series)
        if fault_type:
            filters.append(DiagnosisRecord.fault_type == fault_type)
        if alarm_code:
            filters.append(DiagnosisRecord.alarm_code.ilike(f"%{alarm_code}%"))
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    DiagnosisRecord.trace_id.ilike(pattern),
                    DiagnosisRecord.fault_description.ilike(pattern),
                    DiagnosisRecord.alarm_info.ilike(pattern),
                    DiagnosisRecord.device_name.ilike(pattern),
                    DiagnosisRecord.model.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(DiagnosisRecord)
        list_statement = select(DiagnosisRecord).order_by(DiagnosisRecord.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        records = list(
            self.db.scalars(
                list_statement.offset((page - 1) * page_size).limit(page_size)
            )
        )
        return records, total

    def get_by_trace_id(self, trace_id: str) -> DiagnosisRecord | None:
        statement = select(DiagnosisRecord).where(DiagnosisRecord.trace_id == trace_id)
        return self.db.scalar(statement)

    def list_recent_history_by_device(
        self,
        *,
        device_id: UUID,
        candidate_limit: int = 20,
    ) -> list[DeviceMaintenanceRecord]:
        statement = (
            select(DeviceMaintenanceRecord)
            .where(DeviceMaintenanceRecord.device_id == device_id)
            .order_by(DeviceMaintenanceRecord.completed_at.desc().nullslast(), DeviceMaintenanceRecord.created_at.desc())
            .limit(candidate_limit)
        )
        return list(self.db.scalars(statement))
