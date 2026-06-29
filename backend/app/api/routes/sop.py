from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.sop import SOPExecutionRecordCreate, SOPExecutionRecordUpdate, SOPGenerateRequest, SOPTemplateCreate, SOPTemplateUpdate
from app.services.sop_execution_service import SOPExecutionService, SOPExecutionServiceError
from app.services.sop_service import SOPService, SOPServiceError


router = APIRouter(prefix="/sop", tags=["sop"])


@router.get("/templates")
def list_sop_templates(
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    device_type: str | None = Query(default="pv_inverter"),
    fault_type: str | None = Query(default=None),
    maintenance_level: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = SOPService(db).list_templates(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            fault_type=fault_type,
            maintenance_level=maintenance_level,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except SOPServiceError as exc:
        return error_response(str(exc), 40090)
    return success_response(result)


@router.get("/templates/{template_id}")
def get_sop_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = SOPService(db).get_template(template_id)
    if not result:
        return error_response("SOP template not found", 40490)
    return success_response(result)


@router.post("/templates")
def create_sop_template(
    payload: SOPTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = SOPService(db).create_template(payload, current_user)
    except SOPServiceError as exc:
        return error_response(str(exc), 40091)
    return success_response(result)


@router.put("/templates/{template_id}")
def update_sop_template(
    template_id: UUID,
    payload: SOPTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = SOPService(db).update_template(template_id, payload, current_user)
    except SOPServiceError as exc:
        return error_response(str(exc), 40092)
    return success_response(result)


@router.post("/templates/{template_id}/archive")
def archive_sop_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = SOPService(db).archive_template(template_id, current_user)
    except SOPServiceError as exc:
        return error_response(str(exc), 40093)
    return success_response(result)


@router.post("/generate")
def generate_sop(
    payload: SOPGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = SOPService(db).generate(payload, current_user)
    except SOPServiceError as exc:
        return error_response(str(exc), 40094)
    return success_response(result.model_dump(mode="json"))


@router.get("/executions")
def list_sop_executions(
    template_id: UUID | None = Query(default=None),
    task_id: UUID | None = Query(default=None),
    executor_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = SOPExecutionService(db).list_executions(
            template_id=template_id,
            task_id=task_id,
            executor_id=executor_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    except SOPExecutionServiceError as exc:
        return error_response(str(exc), 40095)
    return success_response(result)


@router.get("/executions/{execution_id}")
def get_sop_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = SOPExecutionService(db).get_execution(execution_id, current_user)
    except SOPExecutionServiceError as exc:
        return error_response(str(exc), 40390)
    if not result:
        return error_response("SOP execution record not found", 40491)
    return success_response(result)


@router.post("/executions")
def create_sop_execution(
    payload: SOPExecutionRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = SOPExecutionService(db).create_execution(payload, current_user)
    except SOPExecutionServiceError as exc:
        return error_response(str(exc), 40096)
    return success_response(result)


@router.put("/executions/{execution_id}")
def update_sop_execution(
    execution_id: UUID,
    payload: SOPExecutionRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = SOPExecutionService(db).update_execution(execution_id, payload, current_user)
    except SOPExecutionServiceError as exc:
        return error_response(str(exc), 40097)
    return success_response(result)
