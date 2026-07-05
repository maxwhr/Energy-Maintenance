from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.multimodal_evidence import (
    MediaAIAnalysisReview,
    MediaEvidenceLinkCreate,
    MediaProcessingJobCreate,
)
from app.services.multimodal_evidence_service import (
    MultimodalEvidenceService,
    MultimodalEvidenceServiceError,
)


router = APIRouter(prefix="/multimodal", tags=["multimodal-evidence"])


@router.get("/media/{media_id}/jobs")
def list_media_jobs(
    media_id: UUID,
    job_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).list_jobs_by_media(
            media_id,
            job_type=job_type,
            status=status,
            page=page,
            page_size=page_size,
        )
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400110)
    return success_response(result)


@router.post("/media/{media_id}/jobs")
def create_media_job(
    media_id: UUID,
    payload: MediaProcessingJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    if payload.mock_run and current_user.role not in {"admin", "expert"}:
        return error_response("Permission denied for mock_run", 403119)
    try:
        result = MultimodalEvidenceService(db).create_processing_job(media_id, payload, current_user)
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400111)
    return success_response(result.model_dump(mode="json"))


@router.get("/jobs/{job_id}")
def get_media_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = MultimodalEvidenceService(db).get_job(job_id)
    if not result:
        return error_response("Media processing job not found", 404110)
    return success_response(result.model_dump(mode="json"))


@router.post("/jobs/{job_id}/cancel")
def cancel_media_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).cancel_job(job_id, current_user)
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400112)
    return success_response(result.model_dump(mode="json"))


@router.get("/media/{media_id}/ocr-results")
def list_media_ocr_results(
    media_id: UUID,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).list_ocr_results(
            media_id,
            status=status,
            page=page,
            page_size=page_size,
        )
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400113)
    return success_response(result)


@router.get("/ocr-results/{result_id}")
def get_ocr_result(
    result_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = MultimodalEvidenceService(db).get_ocr_result(result_id)
    if not result:
        return error_response("OCR result not found", 404111)
    return success_response(result.model_dump(mode="json"))


@router.get("/media/{media_id}/analyses")
def list_media_analyses(
    media_id: UUID,
    human_review_status: str | None = Query(default=None),
    analysis_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).list_ai_analyses(
            media_id,
            human_review_status=human_review_status,
            analysis_type=analysis_type,
            page=page,
            page_size=page_size,
        )
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400114)
    return success_response(result)


@router.get("/analyses/{analysis_id}")
def get_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = MultimodalEvidenceService(db).get_ai_analysis(analysis_id)
    if not result:
        return error_response("AI analysis not found", 404112)
    return success_response(result.model_dump(mode="json"))


@router.post("/analyses/{analysis_id}/review")
def review_analysis(
    analysis_id: UUID,
    payload: MediaAIAnalysisReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).review_ai_analysis(analysis_id, payload, current_user)
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400115)
    return success_response(result.model_dump(mode="json"))


@router.get("/evidence-links")
def list_evidence_links(
    media_id: UUID | None = Query(default=None),
    source_type: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).list_evidence_links(
            media_id=media_id,
            source_type=source_type,
            source_id=source_id,
            page=page,
            page_size=page_size,
        )
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400116)
    return success_response(result)


@router.post("/evidence-links")
def create_evidence_link(
    payload: MediaEvidenceLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).create_evidence_link(payload, current_user)
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400117)
    return success_response(result.model_dump(mode="json"))


@router.get("/media/{media_id}/summary")
def get_media_multimodal_summary(
    media_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = MultimodalEvidenceService(db).get_media_multimodal_summary(media_id)
    except MultimodalEvidenceServiceError as exc:
        return error_response(str(exc), 400118)
    return success_response(result.model_dump(mode="json"))
