from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models import MaintenanceSemanticAnchor, RetrievalDatasetFreeze, RetrievalEvaluationCase, RetrievalEvaluationRun, User
from app.schemas.common import error_response, success_response
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest, RerankRequest
from app.schemas.query_understanding import ClarificationRequest, UnderstandQueryRequest
from app.schemas.retrieval_plan import RetrievalPlanRequest
from app.services.retrieval_service import RetrievalService, RetrievalServiceError
from app.schemas.retrieval_evaluation import RetrievalEvaluationCaseCreate, RetrievalEvaluationRequest
from app.services.retrieval_evaluation_service import RetrievalEvaluationService, RetrievalEvaluationServiceError
from app.schemas.retrieval_pilot import (
    BenchmarkFreezeRequest,
    BenchmarkReviewRequest,
    OfficialPilotRunRequest,
    PilotIndexRequest,
    PilotReconcileRequest,
    PilotRollbackRequest,
    PilotSessionCreate,
)
from app.services.retrieval_pilot_service import RetrievalPilotService, RetrievalPilotServiceError
from app.schemas.retrieval_scope import (
    CHINESE_ENGINEERING_PILOT_SCOPE_ID,
    HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
)
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.query_aware_retrieval_service import QueryAwareRetrievalError, QueryAwareRetrievalService
from app.services.conversation_retrieval_context_service import ConversationContextError


router = APIRouter(prefix="/retrieval", tags=["retrieval"])
R2_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r2"
R3_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r3"
R4_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r4"


def _r2_artifact(name: str) -> dict:
    path = R2_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _r3_artifact(name: str) -> dict:
    path = R3_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _r4_artifact(name: str) -> dict:
    path = R4_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@router.get("/strategy-status")
def retrieval_strategy_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    settings = get_settings()
    latest = db.scalar(select(RetrievalEvaluationRun).where(
        RetrievalEvaluationRun.dataset_version == "task25b-r1-v2"
    ).order_by(RetrievalEvaluationRun.created_at.desc()))
    metrics = latest.metrics_json if latest and latest.metrics_json else {}
    gate = metrics.get("quality_gate") or {}
    return success_response({
        "version": "task25b-r1",
        "default_strategy": settings.RETRIEVAL_DEFAULT_MODE,
        "recommended_strategy": "adaptive" if gate.get("passed") else "keyword",
        "fallback_strategy": "keyword",
        "fallback_reason": "strong_keyword_evidence_protected_or_vector_timeout",
        "quality_gate_status": "PASSED" if gate.get("passed") else settings.RETRIEVAL_QUALITY_GATE_STATUS,
        "blind_test_completed": bool(latest),
        "blind_test_rerun_allowed": False,
        "reranker_enabled": settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
        "reranker_disabled_reason": None if settings.RETRIEVAL_FEATURE_RERANK_ENABLED else "no_measurable_dev_gain",
        "baseline_comparison": (metrics.get("by_mode") or {}),
    })


@router.get("/scope/r1-status")
def retrieval_scope_r1_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
    v1 = db.scalar(select(RetrievalEvaluationRun).where(
        RetrievalEvaluationRun.id == UUID("f1941ec2-9878-45a1-b554-8d9f2f2ec911")
    ))
    v2 = db.scalar(select(RetrievalEvaluationRun).where(
        RetrievalEvaluationRun.name == "task25b_r3_dev_r1_zh_quality_gate_v2"
    ).order_by(RetrievalEvaluationRun.created_at.desc()))
    return success_response({
        "scope": scope.public_dict(), "scope_validation_passed": True,
        "benchmark_dataset_status": "BENCHMARK_DATASET_READY",
        "v1_run": {"run_id": str(v1.id), "preserved": True, "quality_gate_status": "QUALITY_GATE_FAILED"} if v1 else None,
        "v2_run": {"run_id": str(v2.id), "preserved": True, "quality_gate_status": "QUALITY_GATE_FAILED"} if v2 else None,
        "canary_status": "CANARY_PASSED", "full_quality_gate_status": "QUALITY_GATE_FAILED",
        "expert_verified": False,
    })


@router.get("/scope/r2-status")
def retrieval_scope_r2_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    v2 = db.get(RetrievalEvaluationRun, UUID("3e40e25f-f1f1-4146-9e1e-629d2ce76045"))
    v3_cases = list(db.scalars(select(RetrievalEvaluationCase).where(
        RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == "task25b_r3_dev_r2_zh_v3"
    )))
    freeze = db.scalar(select(RetrievalDatasetFreeze).where(
        RetrievalDatasetFreeze.dataset_version == "task25b_r3_dev_r2_zh_v3_test_v3"
    ))
    canary = _r2_artifact("canary_result.json")
    contract = _r2_artifact("metric_contract_audit.json")
    manifest = _r2_artifact("dataset_v3_manifest.json")
    mode = _r2_artifact("mode_distinctness_v2.json")
    return success_response({
        "v2_run": {"run_id": str(v2.id), "preserved": True, "quality_gate_status": "QUALITY_GATE_FAILED"} if v2 else None,
        "v3_dataset": {"dataset_version": "task25b_r3_dev_r2_zh_v3", "cases": len(v3_cases),
                       "frozen": bool(freeze), "freeze_status": freeze.freeze_status if freeze else "NOT_FROZEN",
                       "coverage": manifest.get("test_v3_coverage") or {}},
        "metric_contract": {key: contract.get(key) for key in ("single_relevant_cases", "multi_relevant_cases", "impossible_precision_at_5_cases", "quality_gate_contract_corrected")},
        "canary": {key: canary.get(key) for key in ("status", "passed", "checks", "vector_heavy", "by_mode")},
        "mode_distinctness": {key: mode.get(key) for key in ("keyword_vector_candidate_jaccard_mean", "keyword_vector_rank_correlation_mean", "identical_case_rate", "gate")},
        "quality_gate_status": "NOT_RUN_CANARY_FAILED" if canary and not canary.get("passed") else "PENDING_TEST_V3_FREEZE",
        "expert_verified": False,
    })


@router.get("/scope/r3-status")
def retrieval_scope_r3_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    r2 = _r3_artifact("r2_snapshot.json")
    grounding = _r3_artifact("vector_heavy_grounding.json")
    embedding = _r3_artifact("embedding_pair_diagnostics.json")
    trace = _r3_artifact("dashvector_recall_trace.json")
    anchor_index = _r3_artifact("semantic_anchor_index.json")
    reconciliation = _r3_artifact("semantic_reconciliation.json")
    canary = _r3_artifact("canary_result.json")
    anchor_count = db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor).where(
        MaintenanceSemanticAnchor.namespace == "pilot_r3_semantic",
        MaintenanceSemanticAnchor.index_status == "active",
    )) or 0
    return success_response({
        "r2_canary": {"status": r2.get("r2_canary_status"), "preserved": bool(r2), "read_only": r2.get("read_only")},
        "grounding": {key: grounding.get(key) for key in ("cases_reviewed", "summary", "usable_canary_cases")},
        "embedding": {"pairs": embedding.get("pairs"), "primary_diagnosis": embedding.get("primary_diagnosis"),
                      "averages": embedding.get("averages"), "semantic_minus_raw": embedding.get("semantic_minus_raw")},
        "raw_dashvector": {key: trace.get(key) for key in ("cases", "raw_top50_hit", "post_filter_hit", "mapping_failures", "filter_drops", "content_mismatches", "summary")},
        "semantic_index": {"collection": anchor_index.get("collection"), "raw_partition": "pilot_r2", "semantic_partition": "pilot_r3_semantic",
                           "anchor_vectors": anchor_count, "anchor_types": anchor_index.get("anchor_types") or {},
                           "reconciliation": {key: reconciliation.get(key) for key in ("missing_anchor", "orphan_anchor", "duplicate_anchor_id", "representation_hash_mismatch", "language_leakage", "status_leakage")}},
        "canary": {"status": canary.get("status"), "checks": canary.get("checks") or {}, "vector_heavy": canary.get("vector_heavy") or {},
                    "by_mode": canary.get("by_mode") or {}, "formal_test_v3_1_used": bool(canary.get("formal_test_v3_1_used"))},
        "test_v3_1": {"dataset": None, "frozen": False, "official_run_count": 0, "quality_gate": "NOT_RUN_CANARY_FAILED"},
        "default_partition_changed": False, "pilot_r2_changed": False, "full_reindex": False, "expert_verified": False,
    })


@router.get("/scope/r4-status")
def retrieval_scope_r4_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    manifest = _r4_artifact("semantic_unit_manifest.json")
    quality = _r4_artifact("semantic_unit_quality.json")
    grounding = _r4_artifact("grounding_audit.json")
    index = _r4_artifact("semantic_unit_index.json")
    reconciliation = _r4_artifact("semantic_unit_reconciliation.json")
    margin = _r4_artifact("embedding_margin.json")
    iteration_1 = _r4_artifact("canary_iteration_1.json")
    iteration_2 = _r4_artifact("canary_iteration_2.json")
    canary = iteration_2 or iteration_1
    formal = _r4_artifact("quality_gate_v4.json")
    anchors = list(db.scalars(select(MaintenanceSemanticAnchor).where(
        MaintenanceSemanticAnchor.namespace == "pilot_r4_grounded",
        MaintenanceSemanticAnchor.index_status == "active",
    ).order_by(MaintenanceSemanticAnchor.anchor_type, MaintenanceSemanticAnchor.vector_id)))
    examples = []
    seen_units = set()
    for anchor in anchors:
        unit = (anchor.semantic_fields or {}).get("semantic_unit") or {}
        unit_id = unit.get("semantic_unit_id")
        if not unit_id or unit_id in seen_units:
            continue
        seen_units.add(unit_id)
        examples.append({
            "semantic_unit_id": unit_id, "semantic_unit_type": unit.get("semantic_unit_type"),
            "source_locator": unit.get("source_locator") or anchor.source_locator,
            "anchor_types": unit.get("anchor_types") or [], "quality_status": unit.get("quality_status"),
        })
        if len(examples) == 3:
            break
    score_examples = []
    for row in canary.get("rows") or []:
        if row.get("mode") != "adaptive_grounded":
            continue
        for trace in (row.get("anchor_score_trace") or [])[:1]:
            score_examples.append({
                "semantic_unit_id": trace.get("semantic_unit_id"),
                "anchor_types": trace.get("anchor_types") or [],
                "anchor_scores": trace.get("anchor_scores") or {},
                "final_unit_score": trace.get("final_unit_score"),
                "source_locator": trace.get("source_locator") or {},
            })
        if len(score_examples) == 3:
            break
    return success_response({
        "history": {
            "r2_canary": "CANARY_FAILED", "r3_canary": "CANARY_FAILED",
            "preserved": True, "read_only": True,
        },
        "semantic_units": {
            "documents": manifest.get("documents"), "eligible_sections": manifest.get("eligible_sections"),
            "units": manifest.get("semantic_units"), "unit_types": manifest.get("unit_types") or {},
            "quality_status": "PASSED" if quality.get("passed") else "FAILED", "source_locator_visible": True,
            "examples": examples,
        },
        "grounding": {
            "dataset": grounding.get("dataset"), "total_cases": grounding.get("total_cases"),
            "summary": grounding.get("summary") or {}, "vector_heavy": grounding.get("vector_heavy"),
            "lexical_leakage": grounding.get("lexical_leakage"), "expert_verified": 0,
        },
        "semantic_index": {
            "collection": index.get("collection"), "raw_partition": "pilot_r2",
            "r3_partition": "pilot_r3_semantic", "r4_partition": "pilot_r4_grounded",
            "semantic_units": index.get("semantic_units"), "anchor_vectors": len(anchors),
            "anchor_types": index.get("anchor_types") or {},
            "reconciliation": {key: reconciliation.get(key) for key in (
                "missing", "orphan", "duplicate", "hash_mismatch", "language_leakage", "quality_leakage",
            )},
            "typed_anchor_scores_visible": True, "score_examples": score_examples,
        },
        "embedding_margin": {"status": margin.get("status"), "summary": margin.get("summary") or {}},
        "canary": {
            "status": canary.get("status") or "NOT_RUN", "iteration": canary.get("iteration"),
            "checks": canary.get("checks") or {}, "vector_heavy": canary.get("vector_heavy") or {},
            "by_mode": canary.get("by_mode") or {},
        },
        "formal_v4": {
            "dataset": formal.get("dataset"), "frozen": bool(formal.get("frozen")),
            "run_count": int(formal.get("run_count") or 0),
            "result": formal.get("status") or "NOT_RUN_CANARY_NOT_PASSED",
        },
        "boundaries": {
            "viewer_read_only": True, "pilot_r2_changed": False, "pilot_r3_changed": False,
            "default_partition_changed": False, "original_vectors_reindexed": False,
            "full_reindex": False, "expert_verified": False,
        },
    })


@router.post("/evaluate")
def evaluate_retrieval(
    payload: RetrievalEvaluationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = RetrievalEvaluationService(db).evaluate(payload, current_user)
    except RetrievalEvaluationServiceError as exc:
        return error_response(str(exc), 40075)
    return success_response(result)


@router.get("/evaluation-runs")
def list_evaluation_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalEvaluationService(db).list_runs(page=page, page_size=page_size))


@router.get("/evaluation-runs/{run_id}")
def get_evaluation_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    result = RetrievalEvaluationService(db).get_run(run_id)
    return success_response(result) if result else error_response("Evaluation run not found", 40475)


@router.get("/evaluation-cases")
def list_evaluation_cases(
    dataset_split: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalEvaluationService(db).list_cases(split=dataset_split, page=page, page_size=page_size))


@router.post("/evaluation-cases")
def create_evaluation_case(
    payload: RetrievalEvaluationCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "expert")),
) -> dict:
    try:
        result = RetrievalEvaluationService(db).create_case(payload, current_user)
    except RetrievalEvaluationServiceError as exc:
        return error_response(str(exc), 40076)
    return success_response(result)


@router.post("/query")
def query_retrieval(
    payload: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        route = RetrievalPilotService(db).route_for(current_user, payload.normalized_question)
        resolved_payload = payload.model_copy(update={
            "scope_id": HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
            "manufacturer": "huawei",
            "device_type": "pv_inverter",
        })
        if route.active:
            pilot_mode = route.retrieval_strategy if route.retrieval_strategy in {"vector", "hybrid", "adaptive"} else "adaptive"
            resolved_payload = resolved_payload.model_copy(update={"retrieval_mode": pilot_mode})
        result = RetrievalService(db, allow_real_api=resolved_payload.allow_real_api).query(
            resolved_payload,
            current_user,
        )
        result.retrieval_diagnostics["pilot_route"] = route.model_dump(mode="json")
    except RetrievalServiceError as exc:
        return error_response(str(exc), 40070)
    return success_response(result.model_dump(mode="json"))


@router.post("/understand")
def understand_retrieval_query(
    payload: UnderstandQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    bundle = QueryAwareRetrievalService(db, current_user=current_user).understand(
        payload.query, enable_llm=payload.enable_llm
    )
    return success_response({
        **bundle.understanding.model_dump(mode="json"),
        "clarification": bundle.clarification.model_dump(mode="json"),
        "stage_latency": bundle.stage_latency,
    })


@router.post("/plan")
def plan_retrieval_query(
    payload: RetrievalPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    bundle, plan = QueryAwareRetrievalService(db, current_user=current_user).plan(
        payload.query, enable_llm=payload.enable_llm
    )
    return success_response({
        "understanding": bundle.understanding.model_dump(mode="json"),
        "clarification": bundle.clarification.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
    })


@router.post("/query-aware-search")
def query_aware_search(
    payload: QueryAwareSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = QueryAwareRetrievalService(db, current_user=current_user).search(payload)
    except (QueryAwareRetrievalError, ConversationContextError, ValueError) as exc:
        return error_response(str(exc), 40085)
    return success_response(result.model_dump(mode="json"))


@router.post("/clarify")
def clarify_retrieval_query(
    payload: ClarificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = QueryAwareRetrievalService(db, current_user=current_user).clarify(payload)
    except (ConversationContextError, ValueError) as exc:
        return error_response(str(exc), 40086)
    return success_response(result.model_dump(mode="json"))


@router.post("/rerank")
def rerank_retrieval_candidates(
    payload: RerankRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        result = QueryAwareRetrievalService(db, current_user=current_user).rerank_by_chunk_ids(
            payload.query,
            payload.candidate_chunk_ids,
            enable_llm=payload.enable_llm,
            allow_real_api=payload.allow_real_api,
        )
    except (ValueError, ConversationContextError) as exc:
        return error_response(str(exc), 40087)
    return success_response(result)


@router.get("/pilot/status")
def pilot_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).status())


@router.get("/pilot/u3/status")
def pilot_u3_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).u3_status())


@router.post("/pilot/index")
def pilot_index(
    payload: PilotIndexRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> dict:
    return success_response(RetrievalPilotService(db).pilot_index_preflight(**payload.model_dump()))


@router.get("/pilot/index-runs")
def pilot_index_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).list_index_runs(page=page, page_size=page_size))


@router.post("/pilot/reconcile")
def pilot_reconcile(
    payload: PilotReconcileRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
) -> dict:
    return success_response(RetrievalPilotService(db).reconcile_summary(allow_real_api=payload.allow_real_api))


@router.get("/benchmark/cases")
def benchmark_cases(
    category: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).list_cases(
        category=category, difficulty=difficulty, review_status=review_status, page=page, page_size=page_size
    ))


@router.post("/benchmark/cases/{case_id}/engineering-review")
def engineering_review_case(
    case_id: UUID,
    payload: BenchmarkReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("engineer", "expert", "admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).review_case(case_id, payload, user, expert=False))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40077)


@router.post("/benchmark/cases/{case_id}/expert-review")
def expert_review_case(
    case_id: UUID,
    payload: BenchmarkReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("expert", "admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).review_case(case_id, payload, user, expert=True))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40078)


@router.get("/benchmark/review-progress")
def benchmark_review_progress(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).progress())


@router.post("/benchmark/freeze")
def benchmark_freeze(
    payload: BenchmarkFreezeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).freeze(payload.dataset_version, user))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40079)


@router.get("/benchmark/freezes")
def benchmark_freezes(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(RetrievalPilotService(db).list_freezes())


@router.post("/benchmark/run-official")
def benchmark_run_official(
    payload: OfficialPilotRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).acquire_official_run_lock(payload.dataset_version, user))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40080)


@router.post("/pilot-sessions")
def create_pilot_session(
    payload: PilotSessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("expert", "admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).create_session(payload, user))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40081)


@router.get("/pilot-sessions/{session_id}")
def get_pilot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).get_session(session_id))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40481)


@router.post("/pilot-sessions/{session_id}/activate")
def activate_pilot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).activate_session(session_id, user))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40082)


@router.post("/pilot-sessions/{session_id}/rollback")
def rollback_pilot_session(
    session_id: UUID,
    payload: PilotRollbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).rollback_session(session_id, payload.reason, user))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40083)


@router.post("/pilot-sessions/{session_id}/close")
def close_pilot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
) -> dict:
    try:
        return success_response(RetrievalPilotService(db).close_session(session_id, user))
    except RetrievalPilotServiceError as exc:
        return error_response(str(exc), 40084)


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
