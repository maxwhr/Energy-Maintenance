from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.review import (
    KnowledgeContributionActionRequest,
    KnowledgeContributionCreate,
    KnowledgeContributionUpdate,
)
from app.services.knowledge_contribution_service import (
    KnowledgeContributionPermissionError,
    KnowledgeContributionService,
    KnowledgeContributionServiceError,
)

router = APIRouter(prefix="/knowledge/contributions", tags=["knowledge-contributions"])


@router.get("")
def list_contributions(
    review_status: str | None = Query(default=None),
    contribution_type: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    device_id: UUID | None = Query(default=None),
    submitted_by: UUID | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).list_contributions(
            current_user=current_user,
            review_status=review_status,
            contribution_type=contribution_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_id=device_id,
            submitted_by=submitted_by,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 40095)
    return success_response(data)


@router.post("")
def create_contribution(
    payload: KnowledgeContributionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).create_contribution(payload, current_user=current_user)
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 40395)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 40096)
    return success_response(data)


@router.get("/{contribution_id}")
def get_contribution(
    contribution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).get_contribution(contribution_id, current_user=current_user)
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 40396)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 40496)
    return success_response(data)


@router.put("/{contribution_id}")
def update_contribution(
    contribution_id: UUID,
    payload: KnowledgeContributionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).update_contribution(
            contribution_id,
            payload,
            current_user=current_user,
        )
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 40397)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 40097)
    return success_response(data)


@router.post("/{contribution_id}/submit")
def submit_contribution(
    contribution_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).submit_contribution(contribution_id, current_user=current_user)
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 40398)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 40098)
    return success_response(data)


@router.post("/{contribution_id}/request-changes")
def request_changes(
    contribution_id: UUID,
    payload: KnowledgeContributionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).request_changes(
            contribution_id,
            current_user=current_user,
            comment=payload.comment,
        )
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 40399)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 40099)
    return success_response(data)


@router.post("/{contribution_id}/approve")
def approve_contribution(
    contribution_id: UUID,
    payload: KnowledgeContributionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).approve(
            contribution_id,
            current_user=current_user,
            comment=payload.comment,
        )
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 403100)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 400100)
    return success_response(data)


@router.post("/{contribution_id}/reject")
def reject_contribution(
    contribution_id: UUID,
    payload: KnowledgeContributionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).reject(
            contribution_id,
            current_user=current_user,
            comment=payload.comment,
        )
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 403101)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 400101)
    return success_response(data)


@router.post("/{contribution_id}/convert-to-document")
def convert_contribution(
    contribution_id: UUID,
    payload: KnowledgeContributionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).convert_to_document(
            contribution_id,
            current_user=current_user,
            comment=payload.comment,
        )
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 403102)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 400102)
    return success_response(data)


@router.post("/{contribution_id}/archive")
def archive_contribution(
    contribution_id: UUID,
    payload: KnowledgeContributionActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        data = KnowledgeContributionService(db).archive(
            contribution_id,
            current_user=current_user,
            comment=payload.comment,
        )
    except KnowledgeContributionPermissionError as exc:
        return error_response(str(exc), 403103)
    except KnowledgeContributionServiceError as exc:
        return error_response(str(exc), 400103)
    return success_response(data)
