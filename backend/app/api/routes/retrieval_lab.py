from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import BusinessException
from app.core.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.common import success_response
from app.schemas.retrieval_evaluation import (
    RetrievalEvaluationCaseCreate,
    RetrievalEvaluationRequest,
)
from app.schemas.retrieval_pilot import (
    BenchmarkFreezeRequest,
    BenchmarkReviewRequest,
    OfficialPilotRunRequest,
    PilotIndexRequest,
    PilotReconcileRequest,
    PilotRollbackRequest,
    PilotSessionCreate,
)
from app.services.retrieval_evaluation_service import (
    RetrievalEvaluationService,
    RetrievalEvaluationServiceError,
)
from app.services.retrieval_lab_status_service import RetrievalLabStatusService
from app.services.retrieval_pilot_service import (
    RetrievalPilotService,
    RetrievalPilotServiceError,
)


router = APIRouter(tags=["retrieval-lab"])


@router.get("/retrieval/scope/r1-status")
def retrieval_scope_r1_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalLabStatusService(db).r1_status())


@router.get("/retrieval/scope/r2-status")
def retrieval_scope_r2_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalLabStatusService(db).r2_status())


@router.get("/retrieval/scope/r3-status")
def retrieval_scope_r3_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalLabStatusService(db).r3_status())


@router.get("/retrieval/scope/r4-status")
def retrieval_scope_r4_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalLabStatusService(db).r4_status())


@router.get("/system/retrieval-quality/r5/summary")
def retrieval_scope_r5_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalLabStatusService(db).r5_status())


@router.post("/retrieval/evaluate")
def evaluate_retrieval(
    payload: RetrievalEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = RetrievalEvaluationService(db).evaluate(payload, current_user)
    except RetrievalEvaluationServiceError as exc:
        raise BusinessException.from_service_error(exc, 40075) from exc
    return success_response(result)


@router.get("/retrieval/evaluation-runs")
def list_evaluation_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(
        RetrievalEvaluationService(db).list_runs(
            page=page,
            page_size=page_size,
        )
    )


@router.get("/retrieval/evaluation-runs/{run_id}")
def get_evaluation_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = RetrievalEvaluationService(db).get_run(run_id)
    if not result:
        raise BusinessException(
            "Evaluation run not found",
            40475,
            http_status=404,
        )
    return success_response(result)


@router.get("/retrieval/evaluation-cases")
def list_evaluation_cases(
    dataset_split: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(
        RetrievalEvaluationService(db).list_cases(
            split=dataset_split,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/retrieval/evaluation-cases", status_code=201)
def create_evaluation_case(
    payload: RetrievalEvaluationCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = RetrievalEvaluationService(db).create_case(
            payload,
            current_user,
        )
    except RetrievalEvaluationServiceError as exc:
        raise BusinessException.from_service_error(exc, 40076) from exc
    return success_response(result)


@router.get("/retrieval/pilot/status")
def pilot_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).status())


@router.get("/retrieval/pilot/u3/status")
def pilot_u3_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).u3_status())


@router.post("/retrieval/pilot/index")
def pilot_index(
    payload: PilotIndexRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> dict:
    return success_response(
        RetrievalPilotService(db).pilot_index_preflight(
            **payload.model_dump()
        )
    )


@router.get("/retrieval/pilot/index-runs")
def pilot_index_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(
        RetrievalPilotService(db).list_index_runs(
            page=page,
            page_size=page_size,
        )
    )


@router.post("/retrieval/pilot/reconcile")
def pilot_reconcile(
    payload: PilotReconcileRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> dict:
    return success_response(
        RetrievalPilotService(db).reconcile_summary(
            allow_real_api=payload.allow_real_api
        )
    )


@router.get("/retrieval/benchmark/cases")
def benchmark_cases(
    category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(
        RetrievalPilotService(db).list_cases(
            category=category,
            difficulty=difficulty,
            review_status=review_status,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/retrieval/benchmark/cases/{case_id}/engineering-review")
def engineering_review_case(
    case_id: UUID,
    payload: BenchmarkReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("engineer", "expert", "admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).review_case(
                case_id,
                payload,
                user,
                expert=False,
            )
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40077) from exc


@router.post("/retrieval/benchmark/cases/{case_id}/expert-review")
def expert_review_case(
    case_id: UUID,
    payload: BenchmarkReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("expert", "admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).review_case(
                case_id,
                payload,
                user,
                expert=True,
            )
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40078) from exc


@router.get("/retrieval/benchmark/review-progress")
def benchmark_review_progress(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).progress())


@router.post("/retrieval/benchmark/freeze")
def benchmark_freeze(
    payload: BenchmarkFreezeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).freeze(
                payload.dataset_version,
                user,
            )
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40079) from exc


@router.get("/retrieval/benchmark/freezes")
def benchmark_freezes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).list_freezes())


@router.post("/retrieval/benchmark/run-official")
def benchmark_run_official(
    payload: OfficialPilotRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).acquire_official_run_lock(
                payload.dataset_version,
                user,
            )
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40080) from exc


@router.post("/retrieval/pilot-sessions", status_code=201)
def create_pilot_session(
    payload: PilotSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("expert", "admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).create_session(payload, user)
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40081) from exc


@router.get("/retrieval/pilot-sessions/{session_id}")
def get_pilot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).get_session(session_id)
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40481) from exc


@router.post("/retrieval/pilot-sessions/{session_id}/activate")
def activate_pilot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).activate_session(session_id, user)
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40082) from exc


@router.post("/retrieval/pilot-sessions/{session_id}/rollback")
def rollback_pilot_session(
    session_id: UUID,
    payload: PilotRollbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).rollback_session(
                session_id,
                payload.reason,
                user,
            )
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40083) from exc


@router.post("/retrieval/pilot-sessions/{session_id}/close")
def close_pilot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(
            RetrievalPilotService(db).close_session(session_id, user)
        )
    except RetrievalPilotServiceError as exc:
        raise BusinessException.from_service_error(exc, 40084) from exc
