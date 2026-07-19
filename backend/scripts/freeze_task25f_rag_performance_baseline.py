from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

from task25f_common import (
    BACKEND,
    ROOT,
    RUNTIME,
    aggregate_case_metrics,
    load_suite,
    now_iso,
    read_json,
    run,
    run_case,
    sha256_file,
    sha256_value,
    write_json,
)


FROZEN_FILES = {
    "task25c_report": ROOT / "docs" / "25C_multimodal_cross_modal_diagnosis_report.md",
    "task25c_result": ROOT / ".runtime" / "task25c" / "result.json",
    "task25d_report": ROOT / "docs" / "25D_maintenance_business_workflow_integration_report.md",
    "task25d_regression": ROOT / ".runtime" / "task25d" / "regression.json",
    "task25e_report": ROOT / "docs" / "25E_record_center_performance_and_stability_report.md",
    "task25e_result": ROOT / ".runtime" / "task25e" / "result.json",
    "r6_report": ROOT / "docs" / "25B_R3_DEV_R5_R6_qwen3_dedicated_rerank_report.md",
    "r6_config": ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "config_check.json",
    "r6_probe": ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "qwen_rerank_probe.json",
}


def _zip_inventory() -> list[dict]:
    rows = []
    for path in sorted(ROOT.rglob("*.zip")):
        if ".git" in path.parts:
            continue
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return rows


def _settings_snapshot() -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "query_understanding_runtime_model": settings.RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL,
        "query_understanding_schema_version": settings.RAG_QUERY_UNDERSTANDING_SCHEMA_VERSION,
        "query_weight_original": settings.RAG_QUERY_WEIGHT_ORIGINAL,
        "query_weight_canonical": settings.RAG_QUERY_WEIGHT_CANONICAL,
        "query_weight_intent": settings.RAG_QUERY_WEIGHT_INTENT,
        "query_weight_condition": settings.RAG_QUERY_WEIGHT_CONDITION,
        "deterministic_rerank_enabled": settings.RAG_DETERMINISTIC_RERANK_ENABLED,
        "deterministic_rerank_weights_version": settings.DETERMINISTIC_RERANK_WEIGHTS_VERSION,
        "dedicated_rerank_enabled": settings.RAG_DEDICATED_RERANK_ENABLED,
        "dedicated_rerank_provider": settings.RAG_DEDICATED_RERANK_PROVIDER,
        "dedicated_rerank_model": settings.RAG_DEDICATED_RERANK_MODEL,
        "minimax_tiebreak_enabled": settings.RAG_OPTIONAL_LLM_TIEBREAK_ENABLED,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimension": settings.EMBEDDING_DIM,
        "embedding_cache_ttl_seconds": settings.EMBEDDING_QUERY_CACHE_TTL_SECONDS,
        "embedding_cache_max_entries": settings.EMBEDDING_QUERY_CACHE_MAX_ENTRIES,
        "dashvector_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
        "dashvector_timeout_seconds": settings.DASHVECTOR_TIMEOUT_SECONDS,
        "vector_search_enabled": settings.VECTOR_SEARCH_ENABLED,
        "task25b_allow_real_api": settings.TASK25B_ALLOW_REAL_API,
        "task25b_allow_full_reindex": settings.TASK25B_ALLOW_FULL_REINDEX,
    }


def _database_and_scope() -> tuple[dict, dict]:
    from app.core.database import SessionLocal
    from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
    from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
    from app.services.retrieval_scope_service import RetrievalScopeService

    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        counts = {
            "knowledge_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "approved_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(
                KnowledgeDocument.review_status == "approved"
            )) or 0),
            "knowledge_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
            "active_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk).where(
                KnowledgeChunk.status == "active"
            )) or 0),
            "semantic_anchors": int(db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor)) or 0),
        }
        return counts, scope.public_dict()


def _existing_partition_counts() -> dict:
    candidates = [
        ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "vector_reconciliation.json",
        ROOT / ".runtime" / "task25b_r3_dev_r5_r5" / "vector_reconciliation.json",
        ROOT / ".runtime" / "task25b_r3_dev_r5" / "vector_reconciliation.json",
    ]
    for path in candidates:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return {
                "source": path.relative_to(ROOT).as_posix(),
                "source_sha256": sha256_file(path),
                "snapshot": payload,
            }
    return {"source": None, "source_sha256": None, "snapshot": {}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    immutable_outputs = [
        "baseline.json",
        "baseline_query_results.json",
        "baseline_query_result_hashes.json",
        "baseline_stage_latency.json",
        "baseline_sql_trace.json",
        "baseline_provider_trace.json",
        "baseline_candidate_cardinality.json",
    ]
    if any((RUNTIME / name).exists() for name in immutable_outputs):
        raise SystemExit("Task 25F immutable baseline already exists; refusing to overwrite")

    suite = load_suite()
    progress_path = RUNTIME / "baseline_progress.json"
    progress = read_json(progress_path, {"cases": []}) if args.resume else {"cases": []}
    completed_ids = {item["source_case_id"] for item in progress.get("cases") or [] if not item.get("error")}
    allow_real_api = bool(args.allow_real_api or _settings_snapshot()["task25b_allow_real_api"])
    if not allow_real_api:
        raise SystemExit("Task 25F real baseline requires TASK25B_ALLOW_REAL_API=true or --allow-real-api")

    for index, case in enumerate(suite["rows"], start=1):
        if case["source_case_id"] in completed_ids:
            continue
        try:
            result = run_case(case, allow_real_api=True, cache_mode="off")
        except Exception as exc:  # noqa: BLE001 - preserve the incomplete forensic checkpoint.
            result = {
                "source_case_id": case["source_case_id"],
                "query_hash": case["query_hash"],
                "tags": case.get("tags") or [],
                "error": type(exc).__name__,
            }
        progress["generated_at"] = now_iso()
        progress["dataset_version"] = suite["dataset_version"]
        progress["cases"] = [
            item for item in progress.get("cases") or []
            if item.get("source_case_id") != case["source_case_id"]
        ] + [result]
        write_json(progress_path, progress)
        print(json.dumps({
            "progress": f"{index}/{suite['case_count']}",
            "source_case_id": case["source_case_id"],
            "total_ms": result.get("total_ms"),
            "sql_count": (result.get("sql") or {}).get("count"),
            "provider_requests": (result.get("provider") or {}).get("request_count"),
            "error": result.get("error"),
        }, ensure_ascii=False), flush=True)

    cases = sorted(progress["cases"], key=lambda item: next(
        row["ordinal"] for row in suite["rows"] if row["source_case_id"] == item["source_case_id"]
    ))
    if len(cases) != suite["case_count"] or any(item.get("error") for item in cases):
        raise SystemExit("Task 25F baseline incomplete; rerun with --resume after reviewing baseline_progress.json")

    generated_at = now_iso()
    database_counts, scope = _database_and_scope()
    result_rows = [{
        "source_case_id": item["source_case_id"],
        "query_hash": item["query_hash"],
        "tags": item["tags"],
        "result": item["result"],
    } for item in cases]
    write_json("baseline_query_results.json", {
        "generated_at": generated_at,
        "dataset_version": suite["dataset_version"],
        "cases": result_rows,
    }, overwrite=False)
    write_json("baseline_query_result_hashes.json", {
        "generated_at": generated_at,
        "dataset_version": suite["dataset_version"],
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            "result_hash": item["result_hash"],
            "citation_hash": item["citation_hash"],
        } for item in cases],
    }, overwrite=False)
    write_json("baseline_stage_latency.json", {
        "generated_at": generated_at,
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            "total_ms": item["total_ms"],
            "stage_latency": item["result"]["stage_latency"],
        } for item in cases],
    }, overwrite=False)
    write_json("baseline_sql_trace.json", {
        "generated_at": generated_at,
        "parameter_policy": "SQL parameters and sensitive values are never recorded",
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            **item["sql"],
        } for item in cases],
    }, overwrite=False)
    write_json("baseline_provider_trace.json", {
        "generated_at": generated_at,
        "payload_policy": "API keys, Authorization, vectors, and query text are never recorded",
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            **item["provider"],
        } for item in cases],
        "qwen3_request_count": 0,
        "minimax_rerank_request_count": 0,
        "stepfun_rerank_request_count": 0,
    }, overwrite=False)
    write_json("baseline_candidate_cardinality.json", {
        "generated_at": generated_at,
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            "query_variant_count": len(item["result"]["query_variants"]),
            "candidate_count": len(item["result"]["candidate_identities"]),
            "surfaced_count": len(item["result"]["top10_identities"]),
            "citation_count": len(item["result"]["citation_identities"]),
            "candidate_channel_counts": item["result"]["candidate_channel_counts"],
        } for item in cases],
    }, overwrite=False)

    baseline = {
        "generated_at": generated_at,
        "status": "TASK25F_RAG_BASELINE_FROZEN",
        "performance_suite": {
            "dataset_version": suite["dataset_version"],
            "dataset_sha256": suite["dataset_sha256"],
            "case_count": suite["case_count"],
            "coverage": suite["coverage"],
        },
        "rag_config": _settings_snapshot(),
        "retrieval_scope": scope,
        "database_counts": database_counts,
        "vector_partitions": _existing_partition_counts(),
        "metrics": aggregate_case_metrics(cases),
        "candidate_budget": {
            "query_variant_limit": 5,
            "per_channel_identity_limit": 60,
            "fusion_candidate_limit": 150,
            "candidate_top_k": 50,
            "rrf_k": 60,
        },
        "frozen_evidence": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in FROZEN_FILES.items()
        },
        "alembic": {
            "heads": run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND),
            "current": run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND),
        },
        "backend_env_sha256": sha256_file(BACKEND / ".env"),
        "git_status": run(["git", "status", "--short"], ROOT, timeout=60),
        "staged_files": run(["git", "diff", "--cached", "--name-only"], ROOT, timeout=60),
        "zip_inventory": _zip_inventory(),
        "full_reindex": False,
        "embedding_writes": 0,
        "vector_writes": 0,
        "approval_changes": 0,
        "expert_verified_writes": 0,
    }
    baseline["baseline_query_results_sha256"] = sha256_file(RUNTIME / "baseline_query_results.json")
    baseline["baseline_query_result_hashes_sha256"] = sha256_file(RUNTIME / "baseline_query_result_hashes.json")
    baseline["baseline_sha256"] = sha256_value({key: value for key, value in baseline.items() if key != "baseline_sha256"})
    write_json("baseline.json", baseline, overwrite=False)
    progress_path.unlink(missing_ok=True)
    print(json.dumps({"status": baseline["status"], "metrics": baseline["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
