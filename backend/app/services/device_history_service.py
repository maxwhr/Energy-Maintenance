from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DeviceMaintenanceRecord, User
from app.repositories.device_history_repository import DeviceHistoryRepository
from app.repositories.device_repository import DeviceRepository
from app.schemas.device import DeviceMaintenanceRecordCreate


class DeviceHistoryServiceError(ValueError):
    pass


class DeviceHistoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DeviceHistoryRepository(db)
        self.device_repository = DeviceRepository(db)

    def list_records(
        self,
        *,
        device_id: UUID,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        is_recurrent: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        if not self.device_repository.get_by_id(device_id):
            raise DeviceHistoryServiceError("Device not found")
        self._validate_page(page, page_size)
        records, total = self.repository.list_by_device(
            device_id=device_id,
            fault_type=fault_type,
            alarm_code=alarm_code,
            is_recurrent=is_recurrent,
            page=page,
            page_size=page_size,
        )
        return {
            "items": records,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def create_record(
        self,
        *,
        device_id: UUID,
        payload: DeviceMaintenanceRecordCreate,
        current_user: User,
    ) -> DeviceMaintenanceRecord:
        device = self.device_repository.get_by_id(device_id)
        if not device:
            raise DeviceHistoryServiceError("Device not found")
        if payload.is_recurrent and payload.recurrent_reference_record_id:
            reference_record = self.repository.get_by_id(payload.recurrent_reference_record_id)
            if not reference_record or reference_record.device_id != device_id:
                raise DeviceHistoryServiceError("Recurrent reference record not found")

        completed_at = payload.completed_at or datetime.now(timezone.utc)
        record = DeviceMaintenanceRecord(
            device_id=device_id,
            completed_by=current_user.id,
            completed_at=completed_at,
            **payload.model_dump(exclude={"completed_at"}),
        )
        record = self.repository.create(record)

        device.last_maintenance_at = completed_at
        device.maintenance_count = (device.maintenance_count or 0) + 1
        if payload.fault_type or payload.alarm_code:
            device.fault_count = (device.fault_count or 0) + 1
            device.last_fault_at = completed_at
        self.device_repository.update(device)
        self.db.commit()
        return record

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise DeviceHistoryServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise DeviceHistoryServiceError("page_size must be between 1 and 100")
