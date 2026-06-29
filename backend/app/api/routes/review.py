from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.review import KnowledgeReviewActionRequest
from app.services.review_service import ReviewPermissionError, ReviewService, ReviewServiceError

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/knowledge")
def list_knowledge_for_review(
    review_status: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        data = ReviewService(db).list_knowledge_documents(
            review_status=review_status,
            manufacturer=manufacturer,
            product_series=product_series,
            document_type=document_type,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except ReviewServiceError as exc:
        return error_response(str(exc), 40090)
    return success_response(data)


@router.get("/knowledge/{document_id}")
def get_knowledge_review_detail(
    document_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        data = ReviewService(db).get_knowledge_detail(document_id)
    except ReviewServiceError as exc:
        return error_response(str(exc), 40490)
    return success_response(data)


@router.post("/knowledge/{document_id}/approve")
def approve_knowledge_document(
    document_id: UUID,
    payload: KnowledgeReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = ReviewService(db).approve_document(document_id, comment=payload.comment, reviewer=current_user)
    except ReviewPermissionError as exc:
        return error_response(str(exc), 40390)
    except ReviewServiceError as exc:
        return error_response(str(exc), 40091)
    return success_response(data)


@router.post("/knowledge/{document_id}/reject")
def reject_knowledge_document(
    document_id: UUID,
    payload: KnowledgeReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = ReviewService(db).reject_document(document_id, comment=payload.comment, reviewer=current_user)
    except ReviewPermissionError as exc:
        return error_response(str(exc), 40391)
    except ReviewServiceError as exc:
        return error_response(str(exc), 40092)
    return success_response(data)


@router.post("/knowledge/{document_id}/archive")
def archive_knowledge_document(
    document_id: UUID,
    payload: KnowledgeReviewActionRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = ReviewService(db).archive_document(
            document_id,
            comment=payload.comment if payload else None,
            reviewer=current_user,
        )
    except ReviewPermissionError as exc:
        return error_response(str(exc), 40392)
    except ReviewServiceError as exc:
        return error_response(str(exc), 40093)
    return success_response(data)
