from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user
from app.core.retrieval_lab_config import get_retrieval_lab_settings
from app.models import User
from app.schemas.common import success_response
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest, RerankRequest
from app.schemas.query_understanding import (
    ClarificationRequest,
    UnderstandQueryRequest,
)
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_plan import RetrievalPlanRequest
from app.services.conversation_retrieval_context_service import (
    ConversationContextError,
)
from app.services.query_aware_retrieval_service import (
    QueryAwareRetrievalError,
    QueryAwareRetrievalService,
)
from app.services.retrieval_service import RetrievalService, RetrievalServiceError
from app.services.retrieval_status_service import RetrievalStatusService


router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.get("/strategy-status")
def retrieval_strategy_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalStatusService(db).collect())


@router.post("/query")
def query_retrieval(
    payload: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        resolved_payload = payload
        lab_route = None
        if get_retrieval_lab_settings().ENABLE_RETRIEVAL_LAB:
            from app.services.retrieval_pilot_service import RetrievalPilotService

            lab_route = RetrievalPilotService(db).route_for(
                current_user,
                payload.normalized_question,
            )
            if lab_route.active:
                lab_mode = (
                    lab_route.retrieval_strategy
                    if lab_route.retrieval_strategy
                    in {"vector", "hybrid", "adaptive"}
                    else "adaptive"
                )
                resolved_payload = resolved_payload.model_copy(
                    update={"retrieval_mode": lab_mode}
                )

        result = RetrievalService(
            db,
            allow_real_api=resolved_payload.allow_real_api,
        ).query(
            resolved_payload,
            current_user,
        )
        result.retrieval_diagnostics["lab_route_applied"] = bool(
            lab_route and lab_route.active
        )
        if lab_route is not None:
            result.retrieval_diagnostics["lab_route"] = lab_route.model_dump(
                mode="json"
            )
    except RetrievalServiceError as exc:
        raise BusinessException.from_service_error(exc, 40070) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/understand")
def understand_retrieval_query(
    payload: UnderstandQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    bundle = QueryAwareRetrievalService(
        db,
        current_user=current_user,
    ).understand(
        payload.query,
        enable_llm=payload.enable_llm,
    )
    return success_response(
        {
            **bundle.understanding.model_dump(mode="json"),
            "clarification": bundle.clarification.model_dump(mode="json"),
            "stage_latency": bundle.stage_latency,
        }
    )


@router.post("/plan")
def plan_retrieval_query(
    payload: RetrievalPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    bundle, plan = QueryAwareRetrievalService(
        db,
        current_user=current_user,
    ).plan(
        payload.query,
        enable_llm=payload.enable_llm,
    )
    return success_response(
        {
            "understanding": bundle.understanding.model_dump(mode="json"),
            "clarification": bundle.clarification.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
        }
    )


@router.post("/query-aware-search")
def query_aware_search(
    payload: QueryAwareSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = QueryAwareRetrievalService(
            db,
            current_user=current_user,
        ).search(payload)
    except (
        QueryAwareRetrievalError,
        ConversationContextError,
        ValueError,
    ) as exc:
        raise BusinessException.from_service_error(exc, 40085) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/clarify")
def clarify_retrieval_query(
    payload: ClarificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = QueryAwareRetrievalService(
            db,
            current_user=current_user,
        ).clarify(payload)
    except (ConversationContextError, ValueError) as exc:
        raise BusinessException.from_service_error(exc, 40086) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/rerank")
def rerank_retrieval_candidates(
    payload: RerankRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = QueryAwareRetrievalService(
            db,
            current_user=current_user,
        ).rerank_by_chunk_ids(
            payload.query,
            payload.candidate_chunk_ids,
            enable_llm=payload.enable_llm,
            allow_real_api=payload.allow_real_api,
        )
    except (ValueError, ConversationContextError) as exc:
        raise BusinessException.from_service_error(exc, 40087) from exc
    return success_response(result)


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
        raise BusinessException.from_service_error(exc, 40071) from exc
    return success_response(result)


@router.get("/records/{trace_id}")
def get_retrieval_record(
    trace_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = RetrievalService(db).get_record_detail(trace_id)
    if not result:
        raise BusinessException('Retrieval record not found', 40470, http_status=404)
    return success_response(result)
