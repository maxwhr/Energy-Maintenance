from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, DeviceMaintenanceRecord


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def get_by_code(self, device_code: str) -> Device | None:
        statement = select(Device).where(Device.device_code == device_code)
        return self.db.scalar(statement)

    def list_devices(
        self,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Device], int]:
        filters = []
        if manufacturer:
            filters.append(Device.manufacturer == manufacturer)
        if product_series:
            filters.append(Device.product_series == product_series)
        if device_type:
            filters.append(Device.device_type == device_type)
        if status:
            filters.append(Device.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    Device.device_code.ilike(pattern),
                    Device.device_name.ilike(pattern),
                    Device.model.ilike(pattern),
                    Device.station_name.ilike(pattern),
                    Device.location.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(Device)
        list_statement = select(Device).order_by(Device.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        devices = list(
            self.db.scalars(
                list_statement.offset((page - 1) * page_size).limit(page_size)
            )
        )
        return devices, total

    def create(self, device: Device) -> Device:
        self.db.add(device)
        self.db.flush()
        self.db.refresh(device)
        return device

    def update(self, device: Device) -> Device:
        self.db.add(device)
        self.db.flush()
        self.db.refresh(device)
        return device

    def statistics_summary(self) -> dict[str, int]:
        recent_since = datetime.now(timezone.utc) - timedelta(days=30)
        total_devices = self.db.scalar(select(func.count()).select_from(Device)) or 0
        status_counts = dict(
            self.db.execute(
                select(Device.status, func.count()).group_by(Device.status)
            ).all()
        )
        manufacturer_counts = dict(
            self.db.execute(
                select(Device.manufacturer, func.count()).group_by(Device.manufacturer)
            ).all()
        )
        recent_maintenance_records = (
            self.db.scalar(
                select(func.count())
                .select_from(DeviceMaintenanceRecord)
                .where(DeviceMaintenanceRecord.created_at >= recent_since)
            )
            or 0
        )

        return {
            "total_devices": total_devices,
            "normal_devices": status_counts.get("normal", 0),
            "fault_devices": status_counts.get("fault", 0),
            "maintenance_devices": status_counts.get("maintenance", 0),
            "offline_devices": status_counts.get("offline", 0),
            "retired_devices": status_counts.get("retired", 0),
            "huawei_devices": manufacturer_counts.get("huawei", 0),
            "sungrow_devices": manufacturer_counts.get("sungrow", 0),
            "recent_maintenance_records": recent_maintenance_records,
        }
