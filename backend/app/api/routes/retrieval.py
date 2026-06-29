from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.retrieval import RetrievalQueryRequest
from app.services.retrieval_service import RetrievalService, RetrievalServiceError


router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/query")
def query_retrieval(
    payload: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = RetrievalService(db).query(payload, current_user)
    except RetrievalServiceError as exc:
        return error_response(str(exc), 40070)
    return success_response(result.model_dump(mode="json"))


@router.get("/records")
def list_retrieval_records(
    device_id: UUID | None = Query(default=None),
    manufacturer: str | None = Query(default=None),
    product_series: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = RetrievalService(db).list_records(
            device_id=device_id,
            manufacturer=manufacturer,
            product_series=product_series,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except RetrievalServiceError as exc:
        return error_response(str(exc), 40071)
    return success_response(result)


@router.get("/records/{trace_id}")
def get_retrieval_record(
    trace_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = RetrievalService(db).get_record_detail(trace_id)
    if not result:
        return error_response("Retrieval record not found", 40470)
    return success_response(result)
