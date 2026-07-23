from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import success_response
from app.schemas.maintenance_task import (
    MaintenanceTaskAssignRequest,
    MaintenanceTaskCancelRequest,
    MaintenanceTaskCompleteRequest,
    MaintenanceTaskCreateRequest,
    MaintenanceTaskUpdateRequest,
)
from app.services.maintenance_task_service import MaintenanceTaskService, MaintenanceTaskServiceError


router = APIRouter(prefix="/maintenance/tasks", tags=["maintenance-tasks"])


@router.get("")
def list_maintenance_tasks(
    device_id: UUID | None = Query(default=None),
    assignee_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    fault_type: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = MaintenanceTaskService(db).list_tasks(
            device_id=device_id,
            assignee_id=assignee_id,
            status=status,
            priority=priority,
            fault_type=fault_type,
            alarm_code=alarm_code,
            manufacturer=manufacturer,
            product_series=product_series,
            keyword=keyword,
            page=page,
            page_size=page_size,
            current_user=current_user,
        )
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40100, default_status=400) from exc
    return success_response(result)


@router.get("/statistics/summary")
def get_maintenance_task_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    return success_response(MaintenanceTaskService(db).statistics(current_user))


@router.get("/assignable-users")
def list_assignable_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).list_assignable_users(current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40107, default_status=400) from exc
    return success_response(result)


@router.get("/{task_id}")
def get_maintenance_task_detail(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = MaintenanceTaskService(db).get_detail(task_id, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40310) from exc
    if not result:
        raise BusinessException('Maintenance task not found', 40410, http_status=404)
    return success_response(result)


@router.post("", status_code=201)
def create_maintenance_task(
    payload: MaintenanceTaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).create_task(payload, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40101, default_status=400) from exc
    return success_response(result)


@router.put("/{task_id}")
def update_maintenance_task(
    task_id: UUID,
    payload: MaintenanceTaskUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).update_task(task_id, payload, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40102, default_status=400) from exc
    return success_response(result)


@router.post("/{task_id}/assign")
def assign_maintenance_task(
    task_id: UUID,
    payload: MaintenanceTaskAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).assign_task(task_id, payload, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40103, default_status=400) from exc
    return success_response(result)


@router.post("/{task_id}/start")
def start_maintenance_task(
    task_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).start_task(task_id, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40104, default_status=400) from exc
    return success_response(result)


@router.post("/{task_id}/complete")
def complete_maintenance_task(
    task_id: UUID,
    payload: MaintenanceTaskCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).complete_task(task_id, payload, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40105, default_status=400) from exc
    return success_response(result)


@router.post("/{task_id}/cancel")
def cancel_maintenance_task(
    task_id: UUID,
    payload: MaintenanceTaskCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MaintenanceTaskService(db).cancel_task(task_id, payload, current_user)
    except MaintenanceTaskServiceError as exc:
        raise BusinessException.from_service_error(exc, 40106, default_status=400) from exc
    return success_response(result)
