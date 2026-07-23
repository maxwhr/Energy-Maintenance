from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import success_response
from app.schemas.model_gateway import ModelGatewayChatRequest, ModelGatewayTestRequest
from app.services.model_gateway_service import ModelGatewayService, ModelGatewayServiceError


router = APIRouter(prefix="/model-gateway", tags=["model-gateway"])


@router.get("/status")
def get_model_gateway_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(ModelGatewayService(db).status().model_dump(mode="json"))


@router.post("/test")
def test_model_gateway(
    payload: ModelGatewayTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = ModelGatewayService(db).test(payload, current_user)
    except ModelGatewayServiceError as exc:
        raise BusinessException.from_service_error(exc, 40090) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/chat")
def chat_model_gateway(
    payload: ModelGatewayChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = ModelGatewayService(db).chat(payload, current_user)
    except ModelGatewayServiceError as exc:
        raise BusinessException.from_service_error(exc, 40091) from exc
    return success_response(result.model_dump(mode="json"))


@router.get("/logs")
def list_model_call_logs(
    provider: str | None = Query(default=None),
    model_name: str | None = Query(default=None),
    call_type: str | None = Query(default=None),
    success: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = ModelGatewayService(db).list_logs(
            provider=provider,
            model_name=model_name,
            call_type=call_type,
            success=success,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except ModelGatewayServiceError as exc:
        raise BusinessException.from_service_error(exc, 40092) from exc
    return success_response(result.model_dump(mode="json"))


@router.get("/logs/{log_id}")
def get_model_call_log(
    log_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = ModelGatewayService(db).get_log(log_id)
    if not result:
        raise BusinessException('Model call log not found', 40490, http_status=404)
    return success_response(result.model_dump(mode="json"))
