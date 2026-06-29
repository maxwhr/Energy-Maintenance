from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.correction import CorrectionCreateRequest, CorrectionResolveRequest
from app.services.correction_service import CorrectionPermissionError, CorrectionService, CorrectionServiceError

router = APIRouter(prefix="/corrections", tags=["corrections"])


@router.post("")
def create_correction(
    payload: CorrectionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        data = CorrectionService(db).create_correction(payload, current_user=current_user)
    except CorrectionPermissionError as exc:
        return error_response(str(exc), 40380)
    except CorrectionServiceError as exc:
        return error_response(str(exc), 40080)
    return success_response(data)


@router.get("")
def list_corrections(
    source_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = CorrectionService(db).list_corrections(
            source_type=source_type,
            status=status,
            keyword=keyword,
            current_user=current_user,
            page=page,
            page_size=page_size,
        )
    except CorrectionServiceError as exc:
        return error_response(str(exc), 40081)
    return success_response(data)


@router.get("/{correction_id}")
def get_correction_detail(
    correction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = CorrectionService(db).get_correction(correction_id, current_user=current_user)
    except CorrectionServiceError as exc:
        return error_response(str(exc), 40480)
    return success_response(data)


@router.post("/{correction_id}/resolve")
def resolve_correction(
    correction_id: UUID,
    payload: CorrectionResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = CorrectionService(db).resolve_correction(
            correction_id,
            payload=payload,
            current_user=current_user,
        )
    except CorrectionPermissionError as exc:
        return error_response(str(exc), 40381)
    except CorrectionServiceError as exc:
        return error_response(str(exc), 40082)
    return success_response(data)
