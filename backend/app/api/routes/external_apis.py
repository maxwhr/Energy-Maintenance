from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import success_response
from app.schemas.external_api import (
    ExternalApiDryRunRequest,
    ExternalApiMockRunRequest,
    ExternalApiRealCheckRequest,
    ExternalApiRealRunRequest,
)
from app.services.external_api_gateway import ExternalApiGateway, ExternalApiGatewayError


router = APIRouter(prefix="/external-apis", tags=["external-apis"])


@router.get("/providers")
def list_external_api_providers(
    provider_type: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    items = ExternalApiGateway(db).list_providers(
        provider_type=provider_type,
        enabled=enabled,
        status=status,
    )
    return success_response([item.model_dump(mode="json") for item in items])


@router.get("/providers/{provider_code}")
def get_external_api_provider(
    provider_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    item = ExternalApiGateway(db).get_provider(provider_code)
    if not item:
        raise BusinessException('External API provider not found', 40495, http_status=404)
    return success_response(item.model_dump(mode="json"))


@router.get("/routes")
def list_external_api_routes(
    agent_code: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    capability: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    items = ExternalApiGateway(db).list_routes(agent_code=agent_code, tool_name=tool_name, capability=capability)
    return success_response([item.model_dump(mode="json") for item in items])


@router.get("/status")
def get_external_api_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(ExternalApiGateway(db).status().model_dump(mode="json"))


@router.post("/providers/{provider_code}/check")
def check_external_api_provider(
    provider_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        result = ExternalApiGateway(db).check_provider(provider_code, current_user)
        db.commit()
    except ExternalApiGatewayError as exc:
        db.rollback()
        raise BusinessException.from_service_error(exc, 40095) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/dry-run")
def dry_run_external_api(
    payload: ExternalApiDryRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = ExternalApiGateway(db).dry_run(payload, current_user)
        db.commit()
    except ExternalApiGatewayError as exc:
        db.rollback()
        raise BusinessException.from_service_error(exc, 40096) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/mock-run")
def mock_run_external_api(
    payload: ExternalApiMockRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = ExternalApiGateway(db).mock_run(payload, current_user)
        db.commit()
    except ExternalApiGatewayError as exc:
        db.rollback()
        raise BusinessException.from_service_error(exc, 40099) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/real-run")
def real_run_external_api(
    payload: ExternalApiRealRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = ExternalApiGateway(db).real_run(payload, current_user)
        db.commit()
    except ExternalApiGatewayError as exc:
        db.rollback()
        raise BusinessException.from_service_error(exc, 40100, default_status=400) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/check-real")
def check_real_external_api(
    payload: ExternalApiRealCheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = ExternalApiGateway(db).real_run_provider(
            provider_code=payload.provider_code,
            capability=payload.capability,
            payload=payload.input_summary,
            current_user=current_user,
        )
        db.commit()
    except ExternalApiGatewayError as exc:
        db.rollback()
        raise BusinessException.from_service_error(exc, 40101, default_status=400) from exc
    return success_response(result.model_dump(mode="json"))


@router.get("/logs")
def list_external_api_logs(
    provider_code: str | None = Query(default=None),
    capability: str | None = Query(default=None),
    status: str | None = Query(default=None),
    success: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = ExternalApiGateway(db).list_logs(
            provider_code=provider_code,
            capability=capability,
            status=status,
            success=success,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except ExternalApiGatewayError as exc:
        raise BusinessException.from_service_error(exc, 40097) from exc
    return success_response(result)


@router.get("/logs/{trace_id}")
def get_external_api_log(
    trace_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    item = ExternalApiGateway(db).get_log(trace_id)
    if not item:
        raise BusinessException('External API call log not found', 40496, http_status=404)
    return success_response(item)


@router.get("/health-checks")
def list_external_api_health_checks(
    provider_code: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        result = ExternalApiGateway(db).list_health_checks(
            provider_code=provider_code,
            page=page,
            page_size=page_size,
        )
    except ExternalApiGatewayError as exc:
        raise BusinessException.from_service_error(exc, 40098) from exc
    return success_response(result)
