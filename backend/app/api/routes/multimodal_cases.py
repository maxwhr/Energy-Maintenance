from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.repositories.multimodal_case_repository import MultimodalCaseRepository
from app.schemas.common import success_response
from app.schemas.multimodal_case import (
    EvidenceDecisionRequest,
    MultimodalAnalyzeRequest,
    MultimodalCaseClarify,
    MultimodalCaseCreate,
    MultimodalDiagnoseRequest,
    MultimodalEvidenceRead,
    MultimodalRetrieveRequest,
    MultimodalSopDraftRequest,
    MultimodalTaskDraftRequest,
)
from app.services.media_service import MediaService, MediaServiceError
from app.services.multimodal_case_orchestrator_service import (
    MultimodalCaseOrchestratorError,
    MultimodalCaseOrchestratorService,
)
from app.services.multimodal_case_state_service import (
    MultimodalCaseError,
    MultimodalCasePermissionError,
    MultimodalCaseStateService,
)


router = APIRouter(prefix="/multimodal/cases", tags=["multimodal-maintenance-cases"])




@router.post("", status_code=201)
def create_case(
    payload: MultimodalCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        result = MultimodalCaseStateService(db).create(payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4002501) from exc
    return success_response(result.model_dump(mode="json"))


@router.get("")
def list_cases(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = MultimodalCaseStateService(db).list(
            current_user, status=status, page=page, page_size=page_size
        )
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4002502) from exc
    return success_response(result.model_dump(mode="json"))


@router.get("/{case_id}")
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    service = MultimodalCaseStateService(db)
    try:
        item = service.get(case_id, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4042501) from exc
    return success_response(service.to_read(item).model_dump(mode="json"))


@router.post("/{case_id}/media", status_code=201)
async def upload_case_media(
    case_id: str,
    file: UploadFile = File(...),
    media_type: str = Form("fault_image"),
    description: str | None = Form(default=None),
    manufacturer: str | None = Form(default=None),
    product_series: str | None = Form(default=None),
    device_type: str = Form("unknown"),
    fault_type: str | None = Form(default=None),
    alarm_code: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    state = MultimodalCaseStateService(db)
    try:
        case = state.get(case_id, current_user)
        uploaded = await MediaService(db).upload_media(
            file=file,
            media_type=media_type,
            description=description,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            device_id=case.device_id,
            task_id=None,
            fault_type=fault_type,
            alarm_code=alarm_code,
            current_user=current_user,
        )
        result = MultimodalCaseOrchestratorService(db).attach_media(case, uploaded["media"], current_user)
        result["deduplicated"] = bool(uploaded.get("deduplicated"))
        result["ocr_status"] = uploaded["ocr"].status
    except (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError, MediaServiceError) as exc:
        raise BusinessException.from_service_error(exc, 4002503) from exc
    return success_response(result)


@router.get("/{case_id}/media")
def list_case_media(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        items = MultimodalCaseOrchestratorService(db).list_media(case)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4042502) from exc
    return success_response({"items": items, "total": len(items)})


@router.post("/{case_id}/analyze")
def analyze_case(
    case_id: str,
    payload: MultimodalAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    if payload.mock_run and current_user.role not in {"admin", "expert"}:
        raise BusinessException('mock_run requires expert or admin role', 4032501, http_status=403)
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        result = MultimodalCaseOrchestratorService(db).analyze(case, payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError) as exc:
        raise BusinessException.from_service_error(exc, 4002504) from exc
    return success_response(result)


@router.get("/{case_id}/jobs/{job_id}")
def get_case_job(
    case_id: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4042503) from exc
    if job_id not in (case.analysis_job_ids or []):
        raise BusinessException('Analysis job not found for this case', 4042504, http_status=404)
    run = MultimodalCaseRepository(db).get_agent_run(job_id)
    if not run:
        raise BusinessException('Analysis job not found', 4042504, http_status=404)
    return success_response({
        "job_id": run.run_id,
        "status": run.status,
        "recoverable": run.status in {"FAILED", "PARTIAL"},
        "error_code": run.error_code,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    })


@router.get("/{case_id}/evidence")
def list_case_evidence(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        MultimodalCaseStateService(db).get(case_id, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4042505) from exc
    repository = MultimodalCaseRepository(db)
    evidence = [MultimodalEvidenceRead.model_validate(item).model_dump(mode="json") for item in repository.list_evidence(case_id)]
    conflicts = [{
        "conflict_id": item.conflict_id,
        "conflict_type": item.conflict_type,
        "evidence_ids": item.evidence_ids,
        "severity": item.severity,
        "resolution_required": item.resolution_required,
        "recommended_question": item.recommended_question,
        "resolution_status": item.resolution_status,
    } for item in repository.list_conflicts(case_id)]
    return success_response({"items": evidence, "total": len(evidence), "conflicts": conflicts})


@router.post("/{case_id}/clarify")
def clarify_case(
    case_id: str,
    payload: MultimodalCaseClarify,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    service = MultimodalCaseStateService(db)
    try:
        case = service.get(case_id, current_user)
        result = service.clarify(case, payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4002505) from exc
    return success_response(result.model_dump(mode="json"))


def _decide_evidence(
    case_id: str,
    evidence_id: str,
    payload: EvidenceDecisionRequest,
    db: Session,
    user: User,
    *,
    accept: bool,
) -> dict:
    service = MultimodalCaseStateService(db)
    try:
        case = service.get(case_id, user)
        result = service.decide_evidence(case, evidence_id, payload, user, accept=accept)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4002506 if accept else 4002507) from exc
    return success_response(result.model_dump(mode="json"))


@router.post("/{case_id}/evidence/{evidence_id}/confirm")
def confirm_evidence(
    case_id: str,
    evidence_id: str,
    payload: EvidenceDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    return _decide_evidence(case_id, evidence_id, payload, db, current_user, accept=True)


@router.post("/{case_id}/evidence/{evidence_id}/reject")
def reject_evidence(
    case_id: str,
    evidence_id: str,
    payload: EvidenceDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    return _decide_evidence(case_id, evidence_id, payload, db, current_user, accept=False)


@router.post("/{case_id}/retrieve")
def retrieve_case(
    case_id: str,
    payload: MultimodalRetrieveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        result = MultimodalCaseOrchestratorService(db).retrieve(case, payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError, ValueError) as exc:
        raise BusinessException.from_service_error(exc, 4002508) from exc
    return success_response(result)


@router.post("/{case_id}/diagnose")
def diagnose_case(
    case_id: str,
    payload: MultimodalDiagnoseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        result = MultimodalCaseOrchestratorService(db).diagnose(case, payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError) as exc:
        raise BusinessException.from_service_error(exc, 4002509) from exc
    return success_response(result)


@router.post("/{case_id}/sop-draft")
def create_sop_draft(
    case_id: str,
    payload: MultimodalSopDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        result = MultimodalCaseOrchestratorService(db).create_sop_draft(case, payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError) as exc:
        raise BusinessException.from_service_error(exc, 4002510) from exc
    return success_response(result)


@router.post("/{case_id}/task-draft")
def create_task_draft(
    case_id: str,
    payload: MultimodalTaskDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert", "engineer")),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        result = MultimodalCaseOrchestratorService(db).create_task_draft(case, payload, current_user)
    except (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError) as exc:
        raise BusinessException.from_service_error(exc, 4002511) from exc
    return success_response(result)


@router.get("/{case_id}/audit")
def get_case_audit(
    case_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        case = MultimodalCaseStateService(db).get(case_id, current_user)
        items = MultimodalCaseOrchestratorService(db).audit(case)
    except (MultimodalCaseError, MultimodalCasePermissionError) as exc:
        raise BusinessException.from_service_error(exc, 4042506) from exc
    return success_response({"items": items, "total": len(items)})
