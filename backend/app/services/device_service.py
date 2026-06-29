from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Device
from app.repositories.device_repository import DeviceRepository
from app.schemas.device import DeviceCreate, DeviceUpdate


ALLOWED_MANUFACTURERS = {"huawei", "sungrow"}
ALLOWED_PRODUCT_SERIES = {"SUN2000", "FusionSolar", "SG", "other"}
ALLOWED_DEVICE_TYPES = {"pv_inverter"}
ALLOWED_DEVICE_STATUSES = {"normal", "fault", "maintenance", "offline", "retired"}


class DeviceServiceError(ValueError):
    pass


class DeviceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DeviceRepository(db)

    def get_device(self, device_id: UUID) -> Device | None:
        return self.repository.get_by_id(device_id)

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
    ) -> dict:
        if manufacturer:
            self._validate_manufacturer(manufacturer)
        if product_series:
            self._validate_product_series(product_series)
        if device_type:
            self._validate_device_type(device_type)
        if status:
            self._validate_status(status)
        self._validate_page(page, page_size)

        devices, total = self.repository.list_devices(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": devices,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def create_device(self, payload: DeviceCreate) -> Device:
        self._validate_manufacturer(payload.manufacturer)
        self._validate_product_series(payload.product_series)
        self._validate_device_type(payload.device_type)
        self._validate_status(payload.status)
        if payload.device_code and self.repository.get_by_code(payload.device_code):
            raise DeviceServiceError("device_code already exists")

        device = Device(**payload.model_dump())
        try:
            device = self.repository.create(device)
            self.db.commit()
            return device
        except IntegrityError as exc:
            self.db.rollback()
            raise DeviceServiceError("device_code already exists") from exc

    def update_device(self, device_id: UUID, payload: DeviceUpdate) -> Device:
        device = self.repository.get_by_id(device_id)
        if not device:
            raise DeviceServiceError("Device not found")

        data = payload.model_dump(exclude_unset=True)
        if "manufacturer" in data and data["manufacturer"] is not None:
            self._validate_manufacturer(data["manufacturer"])
        if "product_series" in data:
            self._validate_product_series(data["product_series"])
        if "device_type" in data and data["device_type"] is not None:
            self._validate_device_type(data["device_type"])
        if "status" in data and data["status"] is not None:
            self._validate_status(data["status"])

        for field, value in data.items():
            setattr(device, field, value)

        device = self.repository.update(device)
        self.db.commit()
        return device

    def retire_device(self, device_id: UUID) -> Device:
        device = self.repository.get_by_id(device_id)
        if not device:
            raise DeviceServiceError("Device not found")
        device.status = "retired"
        device = self.repository.update(device)
        self.db.commit()
        return device

    def statistics_summary(self) -> dict[str, int]:
        return self.repository.statistics_summary()

    @staticmethod
    def _validate_manufacturer(manufacturer: str) -> None:
        if manufacturer not in ALLOWED_MANUFACTURERS:
            raise DeviceServiceError("Invalid manufacturer")

    @staticmethod
    def _validate_product_series(product_series: str | None) -> None:
        if product_series and product_series not in ALLOWED_PRODUCT_SERIES:
            raise DeviceServiceError("Invalid product_series")

    @staticmethod
    def _validate_device_type(device_type: str) -> None:
        if device_type not in ALLOWED_DEVICE_TYPES:
            raise DeviceServiceError("Invalid device_type")

    @staticmethod
    def _validate_status(status: str) -> None:
        if status not in ALLOWED_DEVICE_STATUSES:
            raise DeviceServiceError("Invalid status")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise DeviceServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise DeviceServiceError("page_size must be between 1 and 100")
