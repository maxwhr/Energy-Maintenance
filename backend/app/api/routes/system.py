from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import get_settings
from app.core.security_config import collect_security_status
from app.models import (
    DiagnosisRecord,
    KnowledgeChunk,
    KnowledgeDocument,
    MaintenanceTask,
    QARecord,
    SOPTemplate,
    UploadedMedia,
    User,
    RetrievalDatasetFreeze,
    RetrievalEvaluationCase,
    MaintenanceSemanticAnchor,
)
from app.schemas.common import success_response
from app.services.system_statistics_service import SystemStatisticsService
from app.services.multimodal_quality_status_service import MultimodalQualityStatusService
from app.services.maintenance_workflow_status_service import MaintenanceWorkflowStatusService
from app.services.rag_performance_trace_service import RagPerformanceTraceService
from app.services.deployment_readiness_service import DeploymentReadinessService

router = APIRouter(tags=["system"])


@router.get("/system/deployment-readiness")
def get_deployment_readiness(
    current_user: User = Depends(get_current_user),
) -> dict:
    return success_response(DeploymentReadinessService.collect(role=current_user.role))


@router.get("/system/maintenance-workflow/status")
def get_maintenance_workflow_status(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    return success_response(MaintenanceWorkflowStatusService(db).get_status())
R5_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5"
R5_R1_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5_r1"
R5_R2_MM_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5_r2_mm"
R5_R3_MM_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5_r3_mm"
R5_R4_MM_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5_r4_mm"
R5_R5_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5_r5"
R5_R6_RUNTIME = Path(__file__).resolve().parents[4] / ".runtime" / "task25b_r3_dev_r5_r6"


def _r5_artifact(name: str) -> dict:
    path = R5_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _r5_r1_artifact(name: str) -> dict:
    path = R5_R1_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _r5_r2_mm_artifact(name: str) -> dict:
    path = R5_R2_MM_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _r5_r3_mm_artifact(name: str) -> dict:
    path = R5_R3_MM_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _r5_r4_mm_artifact(name: str) -> dict:
    path = R5_R4_MM_RUNTIME / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _runtime_artifact(directory: Path, name: str) -> dict:
    path = directory / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@router.get("/system/info")
def get_system_info() -> dict:
    return success_response(
        {
            "project": "Energy-Maintenance",
            "scope": "Huawei and Sungrow PV inverter maintenance knowledge retrieval and work-assistance system",
            "manufacturers": ["huawei", "sungrow"],
            "device_type": "pv_inverter",
            "product_series": ["SUN2000", "FusionSolar", "SG"],
            "deployment_target": "LoongArch + Kylin native deployment",
            "formal_database": "PostgreSQL",
        }
    )


@router.get("/system/status")
def get_system_status(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    checked_at = datetime.now(timezone.utc).isoformat()
    started_at = perf_counter()
    payload = {
        "service_status": "running",
        "database_status": "offline",
        "database_checked_at": checked_at,
        "database_latency_ms": None,
        "database_error": None,
        "document_count": 0,
        "chunk_count": 0,
        "qa_record_count": 0,
        "diagnosis_record_count": 0,
        "maintenance_task_count": 0,
        "media_count": 0,
        "sop_template_count": 0,
        "security": collect_security_status(get_settings()),
        "retrieval_pilot": {
            "version": "task25b-r2",
            "enabled": settings.TASK25B_R2_PILOT_ENABLED,
            "base_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "pilot_collection": settings.DASHVECTOR_PILOT_COLLECTION,
            "default_strategy": settings.RETRIEVAL_DEFAULT_MODE,
            "pilot_strategy": settings.RETRIEVAL_PILOT_MODE,
            "full_reindex_allowed": settings.TASK25B_ALLOW_FULL_REINDEX,
            "benchmark_candidates": 0,
            "expert_verified": 0,
            "frozen_datasets": 0,
            "chinese_pilot_documents": 0,
            "chinese_pilot_chunks": 0,
            "english_excluded_documents": 0,
            "engineering_approved_documents": 0,
            "pilot_vector_count": 0,
            "language_policy": "zh-CN-primary",
            "retrieval_scope": {
                "scope_id": "chinese_engineering_pilot_r2",
                "normalized_language": "zh-CN",
                "collection_name": settings.DASHVECTOR_PHYSICAL_COLLECTION,
                "partition_name": "pilot_r2",
                "current_version_only": True,
                "include_unknown_language": False,
                "benchmark_dataset_status": "BENCHMARK_DATASET_READY",
                "canary_status": "CANARY_PASSED",
                "quality_gate_status": "QUALITY_GATE_FAILED",
            },
        },
    }

    try:
        db.execute(text("SELECT 1"))
        payload.update(
            {
                "database_status": "online",
                "database_latency_ms": round((perf_counter() - started_at) * 1000, 2),
                "document_count": db.scalar(
                    text("SELECT count(*) FROM knowledge_documents WHERE status != 'deleted'")
                )
                or 0,
                "chunk_count": db.scalar(text("SELECT count(*) FROM knowledge_chunks WHERE status != 'deleted'")) or 0,
                "qa_record_count": db.scalar(select(func.count(QARecord.id))) or 0,
                "diagnosis_record_count": db.scalar(select(func.count(DiagnosisRecord.id))) or 0,
                "maintenance_task_count": db.scalar(select(func.count(MaintenanceTask.id))) or 0,
                "media_count": db.scalar(select(func.count(UploadedMedia.id))) or 0,
                "sop_template_count": db.scalar(select(func.count(SOPTemplate.id))) or 0,
                "retrieval_pilot": {
                    **payload["retrieval_pilot"],
                    "benchmark_candidates": db.scalar(
                        select(func.count(RetrievalEvaluationCase.id)).where(
                            RetrievalEvaluationCase.source_type == "task25b_r2_formal_pilot"
                        )
                    ) or 0,
                    "expert_verified": db.scalar(
                        select(func.count(RetrievalEvaluationCase.id)).where(
                            RetrievalEvaluationCase.source_type == "task25b_r2_formal_pilot",
                            RetrievalEvaluationCase.review_status == "expert_verified",
                        )
                    ) or 0,
                    "frozen_datasets": db.scalar(
                        select(func.count(RetrievalDatasetFreeze.id)).where(
                            RetrievalDatasetFreeze.freeze_status == "frozen"
                        )
                    ) or 0,
                    "chinese_pilot_documents": db.scalar(text(
                        "SELECT count(*) FROM knowledge_documents WHERE metadata_json->>'normalized_language'='zh-CN' "
                        "AND metadata_json->>'engineering_approved_for_pilot'='true' AND metadata_json->>'approved_for_pilot'='true'"
                    )) or 0,
                    "chinese_pilot_chunks": db.scalar(text(
                        "SELECT count(*) FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
                        "WHERE c.status='active' AND d.metadata_json->>'normalized_language'='zh-CN' "
                        "AND d.metadata_json->>'engineering_approved_for_pilot'='true' AND d.metadata_json->>'approved_for_pilot'='true'"
                    )) or 0,
                    "english_excluded_documents": db.scalar(text(
                        "SELECT count(*) FROM knowledge_documents WHERE metadata_json->>'normalized_language'='en' "
                        "AND metadata_json->>'is_default_retrieval_language'='false' AND metadata_json->>'is_pilot_eligible'='false'"
                    )) or 0,
                    "engineering_approved_documents": db.scalar(text(
                        "SELECT count(*) FROM knowledge_documents WHERE metadata_json->>'engineering_approved_for_pilot'='true'"
                    )) or 0,
                    "pilot_vector_count": db.scalar(text(
                        "SELECT count(*) FROM knowledge_chunk_vector_indexes WHERE namespace='pilot_r2' AND index_status='active'"
                    )) or 0,
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 - status endpoint must report DB reachability safely.
        payload["database_latency_ms"] = round((perf_counter() - started_at) * 1000, 2)
        payload["database_error"] = exc.__class__.__name__

    return success_response(payload)


@router.get("/system/statistics")
def get_system_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(SystemStatisticsService(db).collect())


@router.get("/system/multimodal-quality/status")
def get_multimodal_quality_status(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    return success_response(MultimodalQualityStatusService(db).collect())


@router.get("/system/retrieval-performance/summary")
def get_retrieval_performance_summary(
    current_user: User = Depends(get_current_user),
) -> dict:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="admin role required")
    rows = RagPerformanceTraceService.recent()[-50:]
    totals = sorted(float(row.get("total_ms") or 0.0) for row in rows)
    p50 = totals[(len(totals) - 1) // 2] if totals else 0.0
    p95 = totals[max(0, int(len(totals) * 0.95) - 1)] if totals else 0.0
    return success_response({
        "trace_count": len(rows),
        "total_p50_ms": round(p50, 3),
        "total_p95_ms": round(p95, 3),
        "query_text_exposed": False,
        "candidate_content_exposed": False,
        "latest": [{
            "trace_id": row.get("trace_id"),
            "query_hash": row.get("query_hash"),
            "scope_fingerprint": row.get("scope_fingerprint"),
            "mode": row.get("mode"),
            "cache_status": row.get("cache_status"),
            "total_ms": row.get("total_ms"),
            "stages": row.get("stages") or {},
        } for row in rows[-10:]],
    })


@router.get("/system/retrieval-quality/r5/summary")
def get_r5_retrieval_quality_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    semantic = _r5_artifact("semantic_unit_v2_manifest.json")
    audit = _r5_artifact("unrepresented_section_audit.json")
    understanding = _r5_artifact("query_understanding_metrics.json")
    canary = _r5_artifact("canary_result.json")
    reconciliation = _r5_artifact("reconciliation.json")
    formal = _r5_artifact("formal_quality_gate.json")
    r1_baseline = _r5_r1_artifact("r5_failed_baseline.json")
    structured_probe = _r5_r1_artifact("structured_model_probe.json")
    rerank_probe = _r5_r1_artifact("rerank_probe.json")
    raw_vector_probe = _r5_r1_artifact("raw_vector_probe.json")
    r1_canary = _r5_r1_artifact("canary_result.json")
    mm_model = _r5_r2_mm_artifact("minimax_model_probe.json")
    mm_query = _r5_r2_mm_artifact("query_understanding_probe.json")
    mm_tiebreak = _r5_r2_mm_artifact("tiebreak_probe.json")
    mm_deterministic = _r5_r2_mm_artifact("deterministic_rerank_probe.json")
    mm_ab = _r5_r2_mm_artifact("provider_ab_result.json")
    mm_canary = _r5_r2_mm_artifact("canary_result.json")
    mm_formal = _r5_r2_mm_artifact("formal_quality_gate.json")
    mm_reconciliation = _r5_r2_mm_artifact("vector_reconciliation.json")
    mm_latency = _r5_r2_mm_artifact("latency_breakdown.json")
    r3_schema = _r5_r3_mm_artifact("schema_probe.json")
    r3_ab = _r5_r3_mm_artifact("model_ab.json")
    r3_context = _r5_r3_mm_artifact("context_merge_probe.json")
    r3_planner = _r5_r3_mm_artifact("planner_probe.json")
    r3_contract = _r5_r3_mm_artifact("contract_gate.json")
    r3_canary = _r5_r3_mm_artifact("canary_result.json")
    r3_reconciliation = _r5_r3_mm_artifact("vector_reconciliation.json")
    r4_labels = _r5_r4_mm_artifact("label_integrity.json")
    r4_deterministic = _r5_r4_mm_artifact("deterministic_probe.json")
    r4_ambiguity = _r5_r4_mm_artifact("ambiguity_options_probe.json")
    r4_minimax = _r5_r4_mm_artifact("minimax_ambiguity_probe.json")
    r4_canary = (
        _r5_r4_mm_artifact("canary_result.json")
        or _r5_r4_mm_artifact("canary_iteration_2.json")
        or _r5_r4_mm_artifact("canary_iteration_1.json")
    )
    r4_checkpoint = _r5_r4_mm_artifact("canary_checkpoint.json")
    r4_formal = _r5_r4_mm_artifact("formal_quality_gate.json")
    r4_reconciliation = _r5_r4_mm_artifact("vector_reconciliation.json")
    r5_r5_canary = _runtime_artifact(R5_R5_RUNTIME, "canary_iteration_2.json")
    r6_config = _runtime_artifact(R5_R6_RUNTIME, "config_check.json")
    r6_probe = _runtime_artifact(R5_R6_RUNTIME, "qwen_rerank_probe.json")
    r6_canary = (
        _runtime_artifact(R5_R6_RUNTIME, "canary_iteration_2.json")
        or _runtime_artifact(R5_R6_RUNTIME, "canary_iteration_1.json")
    )
    r6_formal = _runtime_artifact(R5_R6_RUNTIME, "formal_quality_gate.json")
    r6_latency = _runtime_artifact(R5_R6_RUNTIME, "latency_breakdown.json")
    r6_vector = _runtime_artifact(R5_R6_RUNTIME, "vector_reconciliation.json")
    r4_iteration_results = [
        item for item in (r4_checkpoint.get("results") or [])
        if int(item.get("iteration") or 0) == 2
    ]
    r3_models = r3_ab.get("models") or {}
    r3_m3 = r3_models.get("MiniMax-M3") or {}
    r3_m27 = r3_models.get("MiniMax-M2.7-highspeed") or {}
    anchor_count = int(db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor).where(
        MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
        MaintenanceSemanticAnchor.index_status == "active",
    )) or 0)
    return success_response({
        "history": {
            "r4_result": "DEVELOPMENT_ENGINEERING_VECTOR_RECALL_NOT_PROVEN",
            "r4_candidate_recall_at_50": 0.80,
            "preserved": True,
        },
        "semantic_unit_v2": {
            "representation_version": "task25b_r3_dev_r5_semantic_unit_v2",
            "units": semantic.get("semantic_units", 0),
            "unit_types": semantic.get("unit_types") or {},
            "source_grounded": semantic.get("source_grounded", False),
            "unsupported_facts": semantic.get("unsupported_facts", 0),
            "audited_sections": audit.get("audited", audit.get("audited_sections", 0)),
            "recovered_sections": audit.get("recovered", audit.get("recovered_sections", 0)),
        },
        "query_understanding": {
            "status": understanding.get("status", "NOT_RUN"),
            "intent_accuracy": understanding.get("intent_accuracy"),
            "model_extraction_accuracy": understanding.get("model_extraction_accuracy"),
            "alarm_extraction_accuracy": understanding.get("alarm_extraction_accuracy"),
            "hallucinated_models": understanding.get("hallucinated_models", 0),
            "hallucinated_alarms": understanding.get("hallucinated_alarms", 0),
            "clarification_precision": understanding.get("clarification_precision"),
            "clarification_recall": understanding.get("clarification_recall"),
        },
        "canary": {
            "status": canary.get("status", "NOT_RUN"),
            "iteration": canary.get("iteration", 0),
            "metrics": canary.get("metrics") or {},
            "multi_query_gain": canary.get("multi_query_gain"),
            "rerank_before_after": canary.get("rerank_before_after") or {},
            "no_answer_f1": (canary.get("metrics") or {}).get("no_answer_f1"),
            "latency": canary.get("latency") or {},
        },
        "semantic_index": {
            "collection": "energy_kn_te_v4_1024_v1",
            "partition": "pilot_r5_query_aware",
            "anchor_vectors": anchor_count,
            "reconciliation": {key: reconciliation.get(key, 0) for key in ("missing", "orphan", "duplicate", "mismatch")},
        },
        "formal_test": {
            "status": formal.get("status") or (
                "NOT_CREATED_CANARY_FAILED"
                if canary.get("status") == "CANARY_FAILED" and int(canary.get("iteration") or 0) >= 2
                else "NOT_CREATED_CANARY_PENDING"
            ),
            "dataset": formal.get("dataset"),
            "frozen": bool(formal.get("frozen")),
            "run_count": int(formal.get("run_count") or 0),
        },
        "boundaries": {
            "viewer_read_only": True,
            "pilot_r2_changed": False,
            "pilot_r3_changed": False,
            "pilot_r4_changed": False,
            "default_partition_changed": False,
            "full_reindex": False,
            "expert_verified": False,
        },
        "r5_r1": {
            "baseline_frozen": bool(r1_baseline),
            "baseline_status": r1_baseline.get("source_result") or "QUERY_AWARE_GROUNDED_RAG_QUALITY_GATE_FAILED",
            "structured_output": {
                "status": structured_probe.get("status", "NOT_RUN"),
                "success": structured_probe.get("structured_success", 0),
                "cases": structured_probe.get("llm_path_cases", len(structured_probe.get("rows") or [])),
            },
            "rerank": {
                "status": rerank_probe.get("status", "NOT_RUN"),
                "success": rerank_probe.get("structured_success", 0),
                "cases": rerank_probe.get("cases", 0),
                "fallback_order_preserved": rerank_probe.get("fallback_order_preserved"),
            },
            "raw_vector": {
                "status": raw_vector_probe.get("status", "NOT_RUN"),
                "raw_hits": raw_vector_probe.get("raw_dashvector_hits", 0),
                "post_filter_hits": raw_vector_probe.get("post_filter_hits", 0),
                "partition": raw_vector_probe.get("partition_name"),
            },
            "kg_alias_status": "DISABLED_DUPLICATE_KEYWORD",
            "rrf_channel_vote_cap": 1,
            "canary_status": r1_canary.get("status", "BLOCKED_BY_RERANK_PROBE"),
            "formal_status": "NOT_CREATED_CANARY_NOT_PASSED",
        },
        "r5_r2_mm": {
            "final_status": (
                "QUERY_AWARE_GROUNDED_RAG_MM_PASS" if mm_formal.get("passed") else
                "QUERY_AWARE_GROUNDED_RAG_MM_QUALITY_GATE_FAILED"
            ),
            "model_probe": {
                "status": "PASSED" if mm_model.get("passed") else mm_model.get("failure_reason", "NOT_RUN"),
                "model": mm_model.get("model"),
                "protocol": mm_model.get("protocol"),
                "service_tier": mm_model.get("service_tier"),
                "thinking_enabled": mm_model.get("thinking_enabled"),
                "tool_use_received": mm_model.get("tool_use_received"),
            },
            "query_understanding": {
                "status": mm_query.get("status", "NOT_RUN"),
                "cases": mm_query.get("minimax_tool_cases", 0),
                "structured_success_ratio": mm_query.get("structured_success_ratio"),
                "hallucinated_models": mm_query.get("hallucinated_models"),
                "hallucinated_alarms": mm_query.get("hallucinated_alarms"),
                "p95_ms": (mm_query.get("latency_ms") or {}).get("p95"),
            },
            "deterministic_rerank": {
                "status": mm_deterministic.get("status", "NOT_RUN"),
                "weights_version": mm_deterministic.get("weights_version"),
                "top1_accuracy": mm_deterministic.get("top1_accuracy"),
                "candidate_boundary_preservation": mm_deterministic.get("candidate_boundary_preservation"),
                "p95_ms": (mm_deterministic.get("latency_ms") or {}).get("p95"),
            },
            "optional_tiebreak": {
                "status": mm_tiebreak.get("status", "NOT_RUN"),
                "real_calls": mm_tiebreak.get("real_calls", 0),
                "structured_success_ratio": mm_tiebreak.get("structured_success_ratio"),
                "fallback_order_preserved": mm_tiebreak.get("simulated_failure_order_preserved"),
                "p95_ms": (mm_tiebreak.get("latency_ms") or {}).get("p95"),
            },
            "provider_ab": {
                "status": mm_ab.get("status", "NOT_RUN"),
                "request_level_chaining": mm_ab.get("request_level_chaining", False),
                "selected_primary_reranker": mm_ab.get("selected_primary_reranker"),
            },
            "circuit_breaker": {
                "query_understanding": ((mm_query.get("circuit_breaker") or {}).get("query_understanding") or {}).get("state"),
                "tiebreak": ((mm_tiebreak.get("circuit_breaker") or {}).get("tiebreak") or {}).get("state"),
            },
            "latency": mm_latency,
            "canary": {
                "status": mm_canary.get("status", "NOT_RUN"),
                "executed_cases": mm_canary.get("executed_cases", 0),
            },
            "formal_test": {
                "status": mm_formal.get("status", "NOT_RUN"),
                "run_count": mm_formal.get("run_count", 0),
            },
            "vector_integrity": {
                "status": mm_reconciliation.get("status", "NOT_RUN"),
                "partition_counts": mm_reconciliation.get("partition_counts") or {},
                "default_partition_affected": mm_reconciliation.get("default_partition_affected"),
                "re_embedded": mm_reconciliation.get("re_embedded", 0),
                "re_upserted": mm_reconciliation.get("re_upserted", 0),
            },
        },
        "r5_r3_mm": {
            "final_status": r3_contract.get("status", "NOT_RUN"),
            "schema_version": r3_ab.get("schema_version", "query_understanding_v2"),
            "schema_probe": {
                "status": r3_schema.get("status", "NOT_RUN"),
                "passed_cases": int(r3_schema.get("passed_cases") or 0),
                "cases": int(r3_schema.get("cases") or 0),
                "nested_retrieval_queries": int(r3_schema.get("nested_retrieval_queries") or 0),
            },
            "model_ab": {
                "same_sample": bool(r3_ab.get("same_sample")),
                "sample_count_per_model": int(r3_ab.get("sample_count_per_model") or 0),
                "selected_runtime_model": r3_ab.get("selected_runtime_model", "deterministic"),
                "selection_reason": r3_ab.get("selection_reason"),
                "m3": {
                    "passed": bool(r3_m3.get("passed")),
                    "structured_success_ratio": r3_m3.get("structured_success_ratio"),
                    "intent_accuracy": r3_m3.get("intent_accuracy"),
                    "canonicalization_accuracy": r3_m3.get("canonicalization_accuracy"),
                    "p95_ms": (r3_m3.get("latency_ms") or {}).get("p95"),
                    "error_rate": r3_m3.get("error_rate"),
                },
                "m27_highspeed": {
                    "passed": bool(r3_m27.get("passed")),
                    "structured_success_ratio": r3_m27.get("structured_success_ratio"),
                    "intent_accuracy": r3_m27.get("intent_accuracy"),
                    "canonicalization_accuracy": r3_m27.get("canonicalization_accuracy"),
                    "p95_ms": (r3_m27.get("latency_ms") or {}).get("p95"),
                    "error_rate": r3_m27.get("error_rate"),
                },
            },
            "context_merge": {
                "status": r3_context.get("status", "NOT_RUN"),
                "accuracy": r3_context.get("accuracy"),
                "passed_cases": int(r3_context.get("passed_cases") or 0),
                "cases": int(r3_context.get("cases") or 0),
            },
            "deterministic_planner": {
                "status": r3_planner.get("status", "NOT_RUN"),
                "passed_cases": int(r3_planner.get("passed_cases") or 0),
                "cases": int(r3_planner.get("cases") or 0),
                "max_query_count": int(r3_planner.get("max_query_count") or 0),
                "original_preservation_ratio": r3_planner.get("original_preservation_ratio"),
            },
            "tie_break_default_enabled": False,
            "contract_gate": {
                "ready": bool(r3_contract.get("ready")),
                "blockers": r3_contract.get("blockers") or [],
            },
            "canary": {
                "status": r3_canary.get("status", "NOT_RUN"),
                "executed_cases": int(r3_canary.get("executed_cases") or 0),
                "iterations_executed": int(r3_canary.get("iterations_executed") or 0),
            },
            "formal_test": {
                "status": "NOT_CREATED_CONTRACT_NOT_READY",
                "run_count": 0,
            },
            "vector_integrity": {
                "status": r3_reconciliation.get("status", "NOT_RUN"),
                "read_only": bool(r3_reconciliation.get("read_only")),
                "partition_counts": r3_reconciliation.get("partition_counts") or {},
                "default_partition_affected": r3_reconciliation.get("default_partition_affected"),
                "re_embedded": int(r3_reconciliation.get("re_embedded") or 0),
                "re_upserted": int(r3_reconciliation.get("re_upserted") or 0),
            },
        },
        "r5_r4_mm": {
            "final_status": r4_canary.get("status", "CANARY_RESUME_PENDING"),
            "labels": {
                "status": r4_labels.get("status", "NOT_RUN"),
                "cases": int(r4_labels.get("case_count") or 0),
                "revised": int(r4_labels.get("revised_count") or 0),
                "source_unchanged": bool(r4_labels.get("source_unchanged")),
            },
            "deterministic_probe": r4_deterministic.get("metrics") or {},
            "ambiguity_probe": r4_ambiguity.get("metrics") or {},
            "minimax_probe": r4_minimax.get("metrics") or {},
            "runtime": {
                "default": "deterministic-first",
                "minimax_role": "optional_ambiguity_resolver",
                "full_query_understanding_llm_required": False,
                "safe_fallback": True,
            },
            "canary": {
                "status": r4_canary.get("status", "RUNNING" if r4_iteration_results else "NOT_RUN"),
                "iteration": int(r4_canary.get("iteration") or (2 if r4_iteration_results else 0)),
                "cases_per_configuration": int(r4_canary.get("cases_per_configuration") or 76),
                "checkpointed_results": len(r4_iteration_results),
                "expected_results": int(r4_canary.get("expected_result_count") or 152),
                "deterministic": (r4_canary.get("deterministic_only") or {}).get("metrics") or {},
                "deterministic_passed": bool((r4_canary.get("deterministic_only") or {}).get("passed")),
                "optional_minimax": (r4_canary.get("optional_minimax") or {}).get("component") or {},
            },
            "formal_test": {
                "status": r4_formal.get("status") or (
                    "NOT_CREATED_DETERMINISTIC_CANARY_FAILED"
                    if int(r4_canary.get("iteration") or 0) >= 2
                    and not bool((r4_canary.get("deterministic_only") or {}).get("passed"))
                    else "NOT_CREATED_CANARY_PENDING"
                ),
                "run_count": int(r4_formal.get("run_count") or 0),
            },
            "vector_integrity": {
                "status": r4_reconciliation.get("status", "PENDING_READ_ONLY_CHECK"),
                "read_only": bool(r4_reconciliation.get("read_only", True)),
                "partition_counts": r4_reconciliation.get("partition_counts") or {},
                "default_partition_affected": bool(r4_reconciliation.get("default_partition_affected", False)),
                "re_embedded": int(r4_reconciliation.get("re_embedded") or 0),
                "re_upserted": int(r4_reconciliation.get("re_upserted") or 0),
            },
            "boundaries": {
                "full_reindex": False,
                "expert_verified": False,
                "approval_changed": False,
                "viewer_read_only": True,
            },
        },
        "r5_r6": {
            "final_status": (
                r6_formal.get("status")
                or r6_canary.get("status")
                or r6_probe.get("status")
                or r6_config.get("status")
                or "QWEN3_RERANK_CONFIG_MISSING"
            ),
            "config": {
                "status": r6_config.get("status", "NOT_CHECKED"),
                "enabled": bool(r6_config.get("enabled")),
                "provider": r6_config.get("provider", "dashscope"),
                "model": r6_config.get("model", "qwen3-rerank"),
                "base_url_exposed": False,
                "api_key_exposed": False,
            },
            "deterministic_baseline": r5_r5_canary.get("metrics") or {},
            "qwen_probe": {
                "status": r6_probe.get("status", "NOT_RUN"),
                "cases": int(r6_probe.get("case_count") or 0),
                "api_success_rate": r6_probe.get("api_success_rate"),
                "metrics": r6_probe.get("metrics") or {},
                "comparison": r6_probe.get("comparison") or {},
            },
            "latency": r6_latency or r6_probe.get("latency") or {},
            "circuit_breaker": r6_probe.get("circuit_breaker") or {"state": "CLOSED"},
            "canary": {
                "status": r6_canary.get("status", "NOT_RUN"),
                "iteration": int(r6_canary.get("iteration") or 0),
                "metrics": r6_canary.get("metrics") or {},
            },
            "formal_test": {
                "status": r6_formal.get("status", "NOT_CREATED_CANARY_NOT_PASSED"),
                "run_count": int(r6_formal.get("run_count") or 0),
            },
            "vector_integrity": {
                "status": r6_vector.get("status", "PENDING_READ_ONLY_CHECK"),
                "partition_counts": r6_vector.get("partition_counts") or {},
                "default_partition_affected": bool(r6_vector.get("default_partition_affected", False)),
                "re_embedded": int(r6_vector.get("re_embedded") or 0),
                "re_upserted": int(r6_vector.get("re_upserted") or 0),
            },
            "runtime": {
                "ranking_path": "qwen3_dedicated_rerank_with_deterministic_fallback",
                "minimax_role": "optional_ambiguity_resolver_only",
                "fallback_order": "deterministic_rerank_v2",
            },
        },
    })
