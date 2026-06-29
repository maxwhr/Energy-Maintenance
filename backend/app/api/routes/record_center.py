from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.common import error_response, success_response
from app.services.record_center_service import RecordCenterService, RecordCenterServiceError

router = APIRouter(prefix="/record-center", tags=["record-center"])


@router.get("/overview")
def get_record_center_overview(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    data = RecordCenterService(db).overview()
    return success_response(data)


@router.get("/search")
def search_records(
    record_type: str = Query(default="all"),
    device_id: UUID | None = Query(default=None),
    keyword: str | None = Query(default=None),
    trace_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    fault_type: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        data = RecordCenterService(db).search(
            record_type=record_type,
            device_id=device_id,
            keyword=keyword,
            trace_id=trace_id,
            status=status,
            fault_type=fault_type,
            alarm_code=alarm_code,
            manufacturer=manufacturer,
            product_series=product_series,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    except RecordCenterServiceError as exc:
        return error_response(str(exc), 40080)
    return success_response(data)


@router.get("/records/{record_type}/{record_id}")
def get_record_detail(
    record_type: str,
    record_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        data = RecordCenterService(db).detail(record_type=record_type, record_id=record_id)
    except RecordCenterServiceError as exc:
        return error_response(str(exc), 40480)
    return success_response(data)


@router.get("/devices/{device_id}/timeline")
def get_device_timeline(
    device_id: UUID,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    record_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        data = RecordCenterService(db).device_timeline(
            device_id=device_id,
            date_from=date_from,
            date_to=date_to,
            record_type=record_type,
            limit=limit,
        )
    except RecordCenterServiceError as exc:
        return error_response(str(exc), 40481)
    return success_response(data)
