from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import KnowledgeChunk, KnowledgeDocument, User
from app.schemas.common import success_response
from app.schemas.knowledge import (
    KnowledgeChunkRead,
    KnowledgeDocumentRead,
    KnowledgeDocumentUploadResponse,
)
from app.services.knowledge_service import KnowledgeService, KnowledgeServiceError

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def document_payload(document: KnowledgeDocument) -> dict:
    data = KnowledgeDocumentRead.model_validate(document).model_dump(mode="json")
    metadata = document.metadata_json or {}
    data["original_file_name"] = metadata.get("original_file_name")
    return data


def chunk_payload(chunk: KnowledgeChunk) -> dict:
    return KnowledgeChunkRead.model_validate(chunk).model_dump(mode="json")


@router.post("/upload", status_code=201)
@router.post("/documents/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    manufacturer: str = Form(...),
    product_series: str = Form(...),
    device_type: str = Form("pv_inverter"),
    document_type: str = Form(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    source: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = await KnowledgeService(db).upload_and_process_document(
            file=file,
            title=title,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            document_type=document_type,
            description=description,
            source=source,
            current_user=current_user,
        )
    except KnowledgeServiceError as exc:
        raise BusinessException.from_service_error(exc, 40020) from exc

    document = result["document"]
    response = KnowledgeDocumentUploadResponse(
        document_id=document.id,
        title=document.title,
        status=document.status,
        parse_status=document.parse_status,
        review_status=document.review_status,
        chunk_count=result["chunk_count"],
        file_name=document.file_name,
        original_file_name=(document.metadata_json or {}).get("original_file_name"),
        warnings=result.get("warnings", []),
    )
    return success_response(response.model_dump(mode="json"))


@router.get("/documents")
def list_documents(
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    document_type: str | None = Query(default=None),
    parse_status: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = KnowledgeService(db).list_documents(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            document_type=document_type,
            parse_status=parse_status,
            review_status=review_status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except KnowledgeServiceError as exc:
        raise BusinessException.from_service_error(exc, 40021) from exc
    return success_response(
        {
            "items": [document_payload(document) for document in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.get("/documents/{document_id}")
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    document = KnowledgeService(db).get_document(document_id)
    if not document:
        raise BusinessException('Knowledge document not found', 40420, http_status=404)
    return success_response(document_payload(document))


@router.get("/documents/{document_id}/chunks")
def list_document_chunks(
    document_id: UUID,
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = KnowledgeService(db).list_document_chunks(
            document_id,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except KnowledgeServiceError as exc:
        raise BusinessException.from_service_error(exc, 40421) from exc
    return success_response(
        {
            "items": [chunk_payload(chunk) for chunk in result["items"]],
            "total": result["total"],
            "page": result["page"],
            "page_size": result["page_size"],
        }
    )


@router.post("/documents/{document_id}/reparse")
def reparse_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = KnowledgeService(db).reparse_document(document_id)
    except KnowledgeServiceError as exc:
        raise BusinessException.from_service_error(exc, 40022) from exc
    document = result["document"]
    response = KnowledgeDocumentUploadResponse(
        document_id=document.id,
        title=document.title,
        status=document.status,
        parse_status=document.parse_status,
        review_status=document.review_status,
        chunk_count=result["chunk_count"],
        file_name=document.file_name,
        original_file_name=(document.metadata_json or {}).get("original_file_name"),
        warnings=result.get("warnings", []),
    )
    return success_response(response.model_dump(mode="json"))


@router.delete("/documents/{document_id}")
def archive_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        document = KnowledgeService(db).archive_document(document_id)
    except KnowledgeServiceError as exc:
        raise BusinessException.from_service_error(exc, 40023) from exc
    return success_response(document_payload(document))
