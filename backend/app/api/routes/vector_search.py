from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.vector_index import IndexRequest, ReindexStaleRequest, VectorIndexRunRead, VectorTestQueryRequest
from app.services.vector_index_service import VectorIndexService, VectorIndexServiceError


router = APIRouter(prefix="/vector-search", tags=["vector-search"])


@router.get("/status")
def get_vector_search_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(VectorIndexService(db).status().model_dump(mode="json"))


@router.get("/runs")
def list_vector_index_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(VectorIndexService(db).list_runs(page=page, page_size=page_size))


@router.get("/runs/{run_id}")
def get_vector_index_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    run = VectorIndexService(db).get_run(run_id)
    if not run:
        return error_response("Vector index run not found", 40480)
    return success_response(VectorIndexRunRead.model_validate(run).model_dump(mode="json"))


@router.get("/documents/{document_id}/status")
def get_document_vector_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(VectorIndexService(db).document_status(document_id).model_dump(mode="json"))


@router.get("/chunks/{chunk_id}/status")
def get_chunk_vector_status(
    chunk_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response([item.model_dump(mode="json") for item in VectorIndexService(db).chunk_status(chunk_id)])


@router.post("/documents/{document_id}/index")
def index_document(
    document_id: UUID,
    payload: IndexRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    payload = payload or IndexRequest()
    try:
        result = VectorIndexService(db).index_document(
            document_id,
            current_user=current_user,
            provider=payload.provider,
            vector_backend=payload.vector_backend,
            force=payload.force,
        )
    except VectorIndexServiceError as exc:
        return error_response(str(exc), 40080)
    return success_response(result.model_dump(mode="json"))


@router.post("/chunks/{chunk_id}/index")
def index_chunk(
    chunk_id: UUID,
    payload: IndexRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    payload = payload or IndexRequest()
    try:
        result = VectorIndexService(db).index_chunk(
            chunk_id,
            current_user=current_user,
            provider=payload.provider,
            vector_backend=payload.vector_backend,
            force=payload.force,
        )
    except VectorIndexServiceError as exc:
        return error_response(str(exc), 40081)
    return success_response(result.model_dump(mode="json"))


@router.post("/reindex-stale")
def reindex_stale(
    payload: ReindexStaleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = VectorIndexService(db).reindex_stale(
            current_user=current_user,
            provider=payload.provider,
            vector_backend=payload.vector_backend,
            limit=payload.limit,
        )
    except VectorIndexServiceError as exc:
        return error_response(str(exc), 40082)
    return success_response(result.model_dump(mode="json"))


@router.post("/test-query")
def test_vector_query(
    payload: VectorTestQueryRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "expert")),
) -> dict:
    result = VectorIndexService(db).test_query(
        payload.text,
        provider=payload.provider,
        vector_backend=payload.vector_backend,
        top_k=payload.top_k,
        filters={
            "manufacturer": payload.manufacturer,
            "product_series": payload.product_series,
            "device_type": payload.device_type,
            "document_type": payload.document_type,
        },
    )
    return success_response(result.model_dump(mode="json"))
