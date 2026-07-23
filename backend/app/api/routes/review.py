from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import success_response
from app.schemas.review import (
    KnowledgeReviewActionRequest,
    VendorOfficialBatchApproveRequest,
    VendorOfficialFlagRequest,
    VendorOfficialWithdrawRequest,
)
from app.services.review_service import ReviewPermissionError, ReviewService, ReviewServiceError

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/knowledge")
def list_knowledge_for_review(
    review_status: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    equipment_category: str | None = Query(default=None),
    quality_status: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    normalized_language: str | None = Query(default=None, pattern="^(zh-CN|en|bilingual|unknown)$"),
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
            equipment_category=equipment_category,
            quality_status=quality_status,
            document_type=document_type,
            keyword=keyword,
            normalized_language=normalized_language,
            page=page,
            page_size=page_size,
        )
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40090) from exc
    return success_response(data)


@router.post("/knowledge/{document_id}/vendor-official-flag")
def flag_vendor_official_document(
    document_id: UUID,
    payload: VendorOfficialFlagRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = ReviewService(db).flag_vendor_official(
            document_id, action=payload.action, comment=payload.comment, reviewer=current_user
        )
    except ReviewPermissionError as exc:
        raise BusinessException.from_service_error(exc, 40395) from exc
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40095) from exc
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
        raise BusinessException.from_service_error(exc, 40490) from exc
    return success_response(data)


@router.post("/knowledge/{document_id}/withdraw-approval")
def withdraw_vendor_official_approval(
    document_id: UUID,
    payload: VendorOfficialWithdrawRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = ReviewService(db).withdraw_vendor_official_approval(
            document_id,
            target_status=payload.target_status,
            reason=payload.reason,
            reviewer=current_user,
        )
    except ReviewPermissionError as exc:
        raise BusinessException.from_service_error(exc, 40396) from exc
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40096) from exc
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
        raise BusinessException.from_service_error(exc, 40390) from exc
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40091) from exc
    return success_response(data)


@router.post("/knowledge/vendor-official/batch-approve-for-pilot")
def batch_approve_vendor_official_for_pilot(
    payload: VendorOfficialBatchApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        data = ReviewService(db).batch_approve_vendor_official(
            payload.document_ids, comment=payload.comment, reviewer=current_user
        )
    except ReviewPermissionError as exc:
        raise BusinessException.from_service_error(exc, 40393) from exc
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40094) from exc
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
        raise BusinessException.from_service_error(exc, 40391) from exc
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40092) from exc
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
        raise BusinessException.from_service_error(exc, 40392) from exc
    except ReviewServiceError as exc:
        raise BusinessException.from_service_error(exc, 40093) from exc
    return success_response(data)
