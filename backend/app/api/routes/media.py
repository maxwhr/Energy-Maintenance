from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.media import MediaUploadResponse
from app.services.media_service import MediaService, MediaServiceError
from app.services.ocr_service import OCRService, OCRServiceError

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    media_type: str = Form("fault_image"),
    description: str | None = Form(default=None),
    manufacturer: str | None = Form(default=None),
    product_series: str | None = Form(default=None),
    device_type: str = Form("pv_inverter"),
    device_id: UUID | None = Form(default=None),
    task_id: UUID | None = Form(default=None),
    fault_type: str | None = Form(default=None),
    alarm_code: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = await MediaService(db).upload_media(
            file=file,
            media_type=media_type,
            description=description,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            device_id=device_id,
            task_id=task_id,
            fault_type=fault_type,
            alarm_code=alarm_code,
            current_user=current_user,
        )
    except MediaServiceError as exc:
        return error_response(str(exc), 40030)

    media = result["media"]
    ocr = result["ocr"]
    response = MediaUploadResponse(
        media_id=media.id,
        media_type=media.media_type,
        description=media.description,
        ocr_text=media.ocr_text or "",
        status=media.status,
        file_name=media.file_name,
        original_file_name=media.original_file_name,
        ocr_status=ocr.status,
        message=ocr.message,
        preview_url=f"/api/media/{media.id}/content",
        manufacturer=media.manufacturer,
        product_series=media.product_series,
        device_type=media.device_type,
        device_id=media.device_id,
        task_id=media.task_id,
        fault_type=(media.metadata_json or {}).get("fault_type"),
        alarm_code=(media.metadata_json or {}).get("alarm_code"),
    )
    return success_response(response.model_dump(mode="json"))


@router.get("/ocr/status")
def get_ocr_status(
    _: User = Depends(get_current_user),
) -> dict:
    result = OCRService().get_status()
    return success_response(result.model_dump(mode="json"))


@router.get("")
def list_media(
    media_type: str | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    device_id: UUID | None = Query(default=None),
    task_id: UUID | None = Query(default=None),
    fault_type: str | None = Query(default=None),
    alarm_code: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = MediaService(db).list_media(
            media_type=media_type,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            device_id=device_id,
            task_id=task_id,
            fault_type=fault_type,
            alarm_code=alarm_code,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except MediaServiceError as exc:
        return error_response(str(exc), 40031)
    return success_response(
        {
            "items": [MediaService(db).media_payload(media) for media in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.post("/{media_id}/ocr")
def recognize_media_ocr(
    media_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = OCRService(db).recognize_media(media_id)
    except OCRServiceError as exc:
        return error_response(str(exc), 40032)
    return success_response(result.model_dump(mode="json"))


@router.get("/{media_id}/ocr")
def get_media_ocr(
    media_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = OCRService(db).get_media_ocr(media_id)
    except OCRServiceError as exc:
        return error_response(str(exc), 40432)
    return success_response(result.model_dump(mode="json"))


@router.get("/{media_id}/content")
def get_media_content(
    media_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    service = MediaService(db)
    media = service.get_media(media_id)
    if not media:
        return error_response("Media item not found", 40430)
    try:
        path = service.resolve_file_path(media)
    except MediaServiceError as exc:
        return error_response(str(exc), 40431)
    return FileResponse(
        path,
        media_type=media.mime_type or "application/octet-stream",
        filename=media.original_file_name or media.file_name,
        content_disposition_type="inline",
    )


@router.get("/{media_id}")
def get_media(
    media_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    service = MediaService(db)
    media = service.get_media(media_id)
    if not media:
        return error_response("Media item not found", 40430)
    return success_response(service.media_payload(media))
