from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.diagnosis import DiagnosisAnalyzeRequest
from app.services.diagnosis_service import DiagnosisService, DiagnosisServiceError


router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


@router.post("/analyze")
def analyze_diagnosis(
    payload: DiagnosisAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = DiagnosisService(db).analyze(payload, current_user)
    except DiagnosisServiceError as exc:
        return error_response(str(exc), 40080)
    return success_response(result.model_dump(mode="json"))


@router.get("/records")
def list_diagnosis_records(
    device_id: UUID | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    fault_type: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = DiagnosisService(db).list_records(
            device_id=device_id,
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            alarm_code=alarm_code,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except DiagnosisServiceError as exc:
        return error_response(str(exc), 40081)
    return success_response(result)


@router.get("/records/{trace_id}")
def get_diagnosis_record(
    trace_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = DiagnosisService(db).get_record_detail(trace_id)
    if not result:
        return error_response("Diagnosis record not found", 40480)
    return success_response(result)
