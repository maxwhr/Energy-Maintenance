from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.agent import (
    AgentApprovalActionRequest,
    AgentArtifactConversionRequest,
    AgentArtifactConversionVoidRequest,
    AgentRunCreateRequest,
    AgentToolExecuteRequest,
)
from app.schemas.common import error_response, success_response
from app.services.agent_approval_service import (
    AgentApprovalPermissionError,
    AgentApprovalService,
    AgentApprovalServiceError,
)
from app.services.agent_artifact_conversion_service import (
    AgentArtifactConversionPermissionError,
    AgentArtifactConversionService,
    AgentArtifactConversionServiceError,
)
from app.services.agent_runtime_service import (
    AgentRuntimePermissionError,
    AgentRuntimeService,
    AgentRuntimeServiceError,
)
from app.services.agent_tool_registry import AgentToolRegistryService


router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/definitions")
def list_agent_definitions(
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    items = AgentToolRegistryService(db).list_definitions(enabled=enabled)
    return success_response([item.model_dump(mode="json") for item in items])


@router.get("/definitions/{agent_code}")
def get_agent_definition(
    agent_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    item = AgentToolRegistryService(db).get_definition(agent_code)
    if not item:
        return error_response("Agent definition not found", 40480)
    return success_response(item.model_dump(mode="json"))


@router.get("/tools")
def list_agent_tools(
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    items = AgentToolRegistryService(db).list_tools(enabled=enabled)
    return success_response([item.model_dump(mode="json") for item in items])


@router.get("/runs")
def list_agent_runs(
    status: str | None = Query(default=None),
    agent_code: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).list_runs(
            current_user=current_user,
            status=status,
            agent_code=agent_code,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40080)
    return success_response(result)


@router.post("/runs")
def create_agent_run(
    payload: AgentRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = AgentRuntimeService(db).create_run(payload, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40380)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40081)
    return success_response(result.model_dump(mode="json"))


@router.get("/runs/{run_id}")
def get_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).get_run_detail(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40381)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40481)
    return success_response(result.model_dump(mode="json"))


@router.get("/runs/{run_id}/timeline")
def get_agent_run_timeline(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).get_run_timeline(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40391)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40491)
    return success_response(result)


@router.post("/runs/{run_id}/cancel")
def cancel_agent_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).cancel_run(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40382)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40082)
    return success_response(result.model_dump(mode="json"))


@router.post("/runs/{run_id}/execute-tool")
def execute_agent_run_tool(
    run_id: str,
    payload: AgentToolExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = AgentRuntimeService(db).execute_tool_for_run(run_id, payload, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40390)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40090)
    return success_response(result.model_dump(mode="json"))


@router.get("/runs/{run_id}/steps")
def list_agent_run_steps(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).list_steps(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40383)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40483)
    return success_response([item.model_dump(mode="json") for item in result])


@router.get("/runs/{run_id}/tool-calls")
def list_agent_run_tool_calls(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).list_tool_calls(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40384)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40484)
    return success_response([item.model_dump(mode="json") for item in result])


@router.get("/runs/{run_id}/approvals")
def list_agent_run_approvals(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).list_approvals(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40385)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40485)
    return success_response([item.model_dump(mode="json") for item in result])


@router.post("/approvals/{approval_id}/approve")
def approve_agent_approval(
    approval_id: UUID,
    payload: AgentApprovalActionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = AgentApprovalService(db).approve(
            approval_id,
            current_user=current_user,
            comment=payload.review_comment if payload else None,
        )
    except AgentApprovalPermissionError as exc:
        return error_response(str(exc), 40386)
    except AgentApprovalServiceError as exc:
        return error_response(str(exc), 40086)
    return success_response(result.model_dump(mode="json"))


@router.post("/approvals/{approval_id}/reject")
def reject_agent_approval(
    approval_id: UUID,
    payload: AgentApprovalActionRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = AgentApprovalService(db).reject(
            approval_id,
            current_user=current_user,
            comment=payload.review_comment if payload else None,
        )
    except AgentApprovalPermissionError as exc:
        return error_response(str(exc), 40387)
    except AgentApprovalServiceError as exc:
        return error_response(str(exc), 40087)
    return success_response(result.model_dump(mode="json"))


@router.get("/runs/{run_id}/artifacts")
def list_agent_run_artifacts(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).list_artifacts(run_id, current_user=current_user)
    except AgentRuntimePermissionError as exc:
        return error_response(str(exc), 40388)
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40488)
    return success_response([item.model_dump(mode="json") for item in result])


@router.get("/events")
def list_agent_events(
    run_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentRuntimeService(db).list_events(
            current_user=current_user,
            run_id=run_id,
            event_type=event_type,
            page=page,
            page_size=page_size,
        )
    except AgentRuntimeServiceError as exc:
        return error_response(str(exc), 40089)
    return success_response(result)


@router.get("/artifacts/{artifact_id}/conversion-status")
def get_agent_artifact_conversion_status(
    artifact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).get_conversion_status(
            artifact_id,
            current_user=current_user,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40392)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40092)
    return success_response(result.model_dump(mode="json"))


@router.post("/artifacts/{artifact_id}/convert")
def convert_agent_artifact(
    artifact_id: UUID,
    payload: AgentArtifactConversionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).convert_artifact(
            artifact_id,
            payload,
            current_user=current_user,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40393)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40093)
    return success_response(result.model_dump(mode="json"))


@router.get("/conversions")
def list_agent_artifact_conversions(
    target_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).list_conversions(
            current_user=current_user,
            target_type=target_type,
            page=page,
            page_size=page_size,
        )
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40094)
    return success_response(result)


@router.get("/runs/{run_id}/conversions")
def list_agent_run_conversions(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).list_run_conversions(
            run_id,
            current_user=current_user,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40396)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40496)
    return success_response([item.model_dump(mode="json") for item in result])


@router.get("/artifacts/{artifact_id}/conversions")
def list_agent_artifact_conversion_history(
    artifact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).list_artifact_conversions(
            artifact_id,
            current_user=current_user,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40397)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40497)
    return success_response([item.model_dump(mode="json") for item in result])


@router.get("/conversions/{conversion_id}/detail")
def get_agent_artifact_conversion_detail(
    conversion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).get_conversion_detail(
            conversion_id,
            current_user=current_user,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40398)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40498)
    return success_response(result.model_dump(mode="json"))


@router.post("/conversions/{conversion_id}/void")
def void_agent_artifact_conversion(
    conversion_id: UUID,
    payload: AgentArtifactConversionVoidRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).void_conversion(
            conversion_id,
            current_user=current_user,
            reason=payload.reason if payload else None,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40399)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40099)
    return success_response(result.model_dump(mode="json"))


@router.get("/conversions/{conversion_trace_id}")
def get_agent_artifact_conversion(
    conversion_trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = AgentArtifactConversionService(db).get_conversion(
            conversion_trace_id,
            current_user=current_user,
        )
    except AgentArtifactConversionPermissionError as exc:
        return error_response(str(exc), 40395)
    except AgentArtifactConversionServiceError as exc:
        return error_response(str(exc), 40495)
    return success_response(result.model_dump(mode="json"))
