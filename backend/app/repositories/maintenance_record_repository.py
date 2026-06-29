from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DeviceMaintenanceRecord


class MaintenanceRecordRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, record_id: UUID) -> DeviceMaintenanceRecord | None:
        return self.db.get(DeviceMaintenanceRecord, record_id)

    def get_by_task_id(self, task_id: UUID) -> DeviceMaintenanceRecord | None:
        statement = select(DeviceMaintenanceRecord).where(DeviceMaintenanceRecord.task_id == task_id)
        return self.db.scalar(statement)

    def create(self, record: DeviceMaintenanceRecord) -> DeviceMaintenanceRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record
