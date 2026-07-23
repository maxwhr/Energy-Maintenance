from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.exceptions import BusinessException
from app.models import User
from app.schemas.device import (
    DeviceCreate,
    DeviceMaintenanceRecordCreate,
    DeviceMaintenanceRecordRead,
    DeviceRead,
    DeviceStatisticsSummary,
    DeviceUpdate,
)
from app.schemas.common import success_response
from app.services.device_history_service import DeviceHistoryService, DeviceHistoryServiceError
from app.services.device_service import DeviceService, DeviceServiceError

router = APIRouter(prefix="/devices", tags=["devices"])

def device_payload(device) -> dict:
    return DeviceRead.model_validate(device).model_dump(mode="json")


def maintenance_record_payload(record) -> dict:
    return DeviceMaintenanceRecordRead.model_validate(record).model_dump(mode="json")


@router.get("/statistics/summary")
def get_device_statistics_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    summary = DeviceService(db).statistics_summary()
    return success_response(
        DeviceStatisticsSummary(**summary).model_dump(mode="json")
    )


@router.get("")
def list_devices(
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = DeviceService(db).list_devices(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except DeviceServiceError as exc:
        raise BusinessException.from_service_error(exc, 40010) from exc
    return success_response(
        {
            "items": [device_payload(device) for device in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        device = DeviceService(db).create_device(payload)
    except DeviceServiceError as exc:
        raise BusinessException.from_service_error(exc, 40011) from exc
    return success_response(device_payload(device))


@router.get("/{device_id}")
def get_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    device = DeviceService(db).get_device(device_id)
    if not device:
        raise BusinessException("Device not found", 40410, http_status=404)
    return success_response(device_payload(device))


@router.put("/{device_id}")
def update_device(
    device_id: UUID,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        device = DeviceService(db).update_device(device_id, payload)
    except DeviceServiceError as exc:
        raise BusinessException.from_service_error(exc, 40012) from exc
    return success_response(device_payload(device))


@router.post("/{device_id}/retire")
def retire_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        device = DeviceService(db).retire_device(device_id)
    except DeviceServiceError as exc:
        raise BusinessException.from_service_error(exc, 40013) from exc
    return success_response(device_payload(device))


@router.get("/{device_id}/maintenance-records")
def list_device_maintenance_records(
    device_id: UUID,
    fault_type: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    is_recurrent: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = DeviceHistoryService(db).list_records(
            device_id=device_id,
            fault_type=fault_type,
            alarm_code=alarm_code,
            is_recurrent=is_recurrent,
            page=page,
            page_size=page_size,
        )
    except DeviceHistoryServiceError as exc:
        raise BusinessException.from_service_error(exc, 40014) from exc
    return success_response(
        {
            "items": [maintenance_record_payload(record) for record in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.post(
    "/{device_id}/maintenance-records",
    status_code=status.HTTP_201_CREATED,
)
def create_device_maintenance_record(
    device_id: UUID,
    payload: DeviceMaintenanceRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        record = DeviceHistoryService(db).create_record(
            device_id=device_id,
            payload=payload,
            current_user=current_user,
        )
    except DeviceHistoryServiceError as exc:
        raise BusinessException.from_service_error(exc, 40015) from exc
    return success_response(maintenance_record_payload(record))
