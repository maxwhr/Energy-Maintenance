from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DeviceMaintenanceRecord


class DeviceHistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, record_id: UUID) -> DeviceMaintenanceRecord | None:
        return self.db.get(DeviceMaintenanceRecord, record_id)

    def list_by_device(
        self,
        *,
        device_id: UUID,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        is_recurrent: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[DeviceMaintenanceRecord], int]:
        filters = [DeviceMaintenanceRecord.device_id == device_id]
        if fault_type:
            filters.append(DeviceMaintenanceRecord.fault_type == fault_type)
        if alarm_code:
            filters.append(DeviceMaintenanceRecord.alarm_code == alarm_code)
        if is_recurrent is not None:
            filters.append(DeviceMaintenanceRecord.is_recurrent == is_recurrent)

        count_statement = select(func.count()).select_from(DeviceMaintenanceRecord).where(*filters)
        list_statement = (
            select(DeviceMaintenanceRecord)
            .where(*filters)
            .order_by(DeviceMaintenanceRecord.completed_at.desc().nullslast(), DeviceMaintenanceRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        total = self.db.scalar(count_statement) or 0
        records = list(self.db.scalars(list_statement))
        return records, total

    def create(self, record: DeviceMaintenanceRecord) -> DeviceMaintenanceRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record
