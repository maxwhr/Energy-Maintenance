from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import error_response, success_response
from app.schemas.maintenance_workflow import (
    DiagnosisConfirmationRequest,
    DiagnosisDraftRequest,
    FormalTaskCreationRequest,
    MaintenanceWorkflowCreate,
    WorkflowAdminActionRequest,
    WorkflowCorrectionCandidateRequest,
    WorkflowSopDraftRequest,
    WorkflowSopReviewRequest,
    WorkflowTaskActionRequest,
    WorkflowTaskCompleteRequest,
    WorkflowTaskDraftRequest,
    WorkflowTaskRecordCreate,
    WorkflowTaskStepUpdate,
    WorkflowTaskVerificationRequest,
)
from app.services.diagnosis_confirmation_service import DiagnosisConfirmationService
from app.services.formal_task_creation_service import FormalTaskCreationService
from app.services.maintenance_workflow_service import (
    MaintenanceWorkflowError,
    MaintenanceWorkflowPermissionError,
    MaintenanceWorkflowService,
)
from app.services.task_completion_verification_service import TaskCompletionVerificationService
from app.services.task_execution_record_service import TaskExecutionRecordService
from app.services.workflow_correction_service import WorkflowCorrectionService
from app.services.workflow_diagnosis_service import WorkflowDiagnosisService
from app.services.workflow_sop_service import WorkflowSopService


router = APIRouter(prefix="/maintenance-workflows", tags=["maintenance-workflows"])
WRITE_USER = require_roles("admin", "expert", "engineer")


def _service_error(exc: Exception, code: int) -> dict:
    return error_response(str(exc), code)


@router.post("")
def create_workflow(
    payload: MaintenanceWorkflowCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(WRITE_USER),
) -> dict:
    try:
        return success_response(MaintenanceWorkflowService(db).create(payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002701)


@router.get("")
def list_workflows(
    status: str | None = Query(default=None),
    device_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = MaintenanceWorkflowService(db).list(
            user=current_user,
            status=status,
            device_id=device_id,
            page=page,
            page_size=page_size,
        )
        return success_response(result)
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002702)


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return success_response(MaintenanceWorkflowService(db).detail(workflow_id, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4042701)


@router.get("/{workflow_id}/status")
def get_workflow_status(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return success_response(MaintenanceWorkflowService(db).status(workflow_id, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4042702)


@router.get("/{workflow_id}/timeline")
def get_workflow_timeline(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return success_response(MaintenanceWorkflowService(db).timeline(workflow_id, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4042703)


@router.post("/{workflow_id}/diagnosis-draft")
def create_diagnosis_draft(
    workflow_id: str,
    payload: DiagnosisDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(WRITE_USER),
) -> dict:
    try:
        return success_response(WorkflowDiagnosisService(db).create_draft(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002703)


@router.post("/{workflow_id}/diagnosis-confirm")
def confirm_diagnosis(
    workflow_id: str,
    payload: DiagnosisConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(WRITE_USER),
) -> dict:
    try:
        return success_response(DiagnosisConfirmationService(db).confirm(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002704)


@router.post("/{workflow_id}/sop-draft")
def create_sop_draft(
    workflow_id: str,
    payload: WorkflowSopDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(WRITE_USER),
) -> dict:
    try:
        return success_response(WorkflowSopService(db).create_draft(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002705)


@router.post("/{workflow_id}/sop-review")
def review_sop(
    workflow_id: str,
    payload: WorkflowSopReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(WRITE_USER),
) -> dict:
    try:
        return success_response(WorkflowSopService(db).review(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002706)


@router.post("/{workflow_id}/task-draft")
def create_task_draft(
    workflow_id: str,
    payload: WorkflowTaskDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(WRITE_USER),
) -> dict:
    try:
        return success_response(FormalTaskCreationService(db).create_task_draft(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002707)


@router.post("/{workflow_id}/formal-task")
def create_formal_task(
    workflow_id: str,
    payload: FormalTaskCreationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "engineer")),
) -> dict:
    try:
        return success_response(FormalTaskCreationService(db).create_formal_task(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002708)


@router.post("/{workflow_id}/task/start")
def start_task(workflow_id: str, payload: WorkflowTaskActionRequest, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskExecutionRecordService(db).start(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002709)


@router.post("/{workflow_id}/task/pause")
def pause_task(workflow_id: str, payload: WorkflowTaskActionRequest, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskExecutionRecordService(db).pause(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002710)


@router.post("/{workflow_id}/task/resume")
def resume_task(workflow_id: str, payload: WorkflowTaskActionRequest, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskExecutionRecordService(db).resume(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002711)


@router.post("/{workflow_id}/task/records")
def add_task_record(workflow_id: str, payload: WorkflowTaskRecordCreate, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskExecutionRecordService(db).add_record(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002712)


@router.post("/{workflow_id}/task/steps/{step_id}")
def update_task_step(workflow_id: str, step_id: UUID, payload: WorkflowTaskStepUpdate, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskExecutionRecordService(db).update_step(workflow_id, step_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002713)


@router.post("/{workflow_id}/task/verify")
def verify_task(workflow_id: str, payload: WorkflowTaskVerificationRequest, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskCompletionVerificationService(db).verify(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002714)


@router.post("/{workflow_id}/task/complete")
def complete_task(workflow_id: str, payload: WorkflowTaskCompleteRequest, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(TaskCompletionVerificationService(db).complete(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002715)


@router.post("/{workflow_id}/correction-candidate")
def create_correction_candidate(workflow_id: str, payload: WorkflowCorrectionCandidateRequest, db: Session = Depends(get_db), current_user: User = Depends(WRITE_USER)) -> dict:
    try:
        return success_response(WorkflowCorrectionService(db).create_candidate(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002716)


@router.get("/{workflow_id}/corrections")
def list_corrections(workflow_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict:
    try:
        return success_response(WorkflowCorrectionService(db).list_candidates(workflow_id, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4042704)


@router.post("/{workflow_id}/admin-action")
def admin_workflow_action(workflow_id: str, payload: WorkflowAdminActionRequest, db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))) -> dict:
    try:
        return success_response(MaintenanceWorkflowService(db).admin_action(workflow_id, payload, current_user))
    except (MaintenanceWorkflowError, MaintenanceWorkflowPermissionError) as exc:
        return _service_error(exc, 4002717)
