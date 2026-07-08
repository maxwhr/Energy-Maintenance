from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
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


@router.post("/query/stream")
def stream_retrieval(
    payload: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    payload_data = payload.model_dump()
    payload_data["enable_model_enhancement"] = True
    if payload.model_provider == "rule_based":
        payload_data["model_provider"] = "cloud_openai"
    stream_payload = RetrievalQueryRequest(**payload_data)

    def event_stream():
        try:
            for event in RetrievalService(db).query_stream_events(stream_payload, current_user):
                event_type = str(event.get("type") or "message")
                yield _sse_event(event_type, event)
        except RetrievalServiceError as exc:
            yield _sse_event("error", {"type": "error", "message": str(exc), "code": 40072})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
