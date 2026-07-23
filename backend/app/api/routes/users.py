from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.exceptions import BusinessException
from app.models.system import User
from app.schemas.auth import UserCreateRequest, UserManagementRead, UserUpdateRequest
from app.schemas.common import success_response
from app.services.user_service import UserService, UserServiceError

router = APIRouter(prefix="/users", tags=["users"])

def user_payload(user: User) -> dict:
    return UserManagementRead.model_validate(user).model_dump(mode="json")


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        user = UserService(db).create_user(payload)
    except UserServiceError as exc:
        raise BusinessException.from_service_error(exc, 40001) from exc
    return success_response(user_payload(user))


@router.get("")
def list_users(
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        result = UserService(db).list_users(
            role=role,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except UserServiceError as exc:
        raise BusinessException.from_service_error(exc, 40002) from exc
    return success_response(
        {
            "items": [user_payload(user) for user in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.get("/{user_id}")
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    user = UserService(db).get_user(user_id)
    if not user:
        raise BusinessException("User not found", 40401, http_status=404)
    return success_response(user_payload(user))


@router.put("/{user_id}")
def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        user = UserService(db).update_user(user_id, payload)
    except UserServiceError as exc:
        raise BusinessException.from_service_error(exc, 40003) from exc
    return success_response(user_payload(user))


@router.post("/{user_id}/disable")
def disable_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        user = UserService(db).disable_user(user_id)
    except UserServiceError as exc:
        raise BusinessException.from_service_error(exc, 40004) from exc
    return success_response(user_payload(user))


@router.post("/{user_id}/enable")
def enable_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    try:
        user = UserService(db).enable_user(user_id)
    except UserServiceError as exc:
        raise BusinessException.from_service_error(exc, 40005) from exc
    return success_response(user_payload(user))
