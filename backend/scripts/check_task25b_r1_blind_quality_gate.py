from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from task25b_r1_common import BACKEND, ROOT, RUNTIME, now_iso, sha256_file, sha256_text, write_json
from task25b_r1_eval_common import evaluate_split, load_cases
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationResult, RetrievalEvaluationRun


FROZEN_MANIFEST = RUNTIME / "test_v2_frozen_manifest.json"
FROZEN_LABELS = RUNTIME / "test_v2_labels_frozen.json"
STARTED = RUNTIME / "blind_run_started.json"
RESULT = RUNTIME / "blind_quality_gate.json"


def _current_label_hash() -> str:
    with SessionLocal() as db:
        cases = load_cases(db, "test_v2", allow_blind=True)
        labels = [{
            "case_id": str(item.id), "case_name": item.name, "category": item.category,
            "query_sha256": sha256_text(item.query_text),
            "expected_document_ids": sorted(str(value) for value in (item.expected_document_ids or [])),
            "expected_chunk_ids": sorted(str(value) for value in (item.expected_chunk_ids or [])),
            "expected_media_ids": sorted(str(value) for value in (item.expected_media_ids or [])),
            "required_filters": item.required_filters or {}, "difficulty": item.difficulty,
        } for item in cases]
    canonical = json.dumps(labels, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(canonical)


def _label_leakage_scan(expected_ids: set[str]) -> dict:
    matches = []
    roots = [BACKEND / "app", BACKEND / "tests", BACKEND / "scripts"]
    excluded = {"check_task25b_r1_blind_quality_gate.py", "freeze_task25b_r1_test_v2.py"}
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".md", ".ts", ".vue"} or path.name in excluded:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(value in text for value in expected_ids):
                matches.append(str(path.relative_to(ROOT)))
    return {"passed": not matches, "matching_files": matches}


def _persist_run(evaluation: dict, gate: dict) -> str:
    settings = get_settings()
    with SessionLocal() as db:
        case_map = {str(item.id): item for item in load_cases(db, "test_v2", allow_blind=True)}
        run = RetrievalEvaluationRun(
            name="Task 25B-R1 frozen test_v2 blind quality gate",
            embedding_provider=settings.EMBEDDING_PROVIDER, embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIM, vector_backend=settings.VECTOR_BACKEND,
            collection_name=settings.DASHVECTOR_R1_CANARY_COLLECTION,
            retrieval_config_json={
                "modes": evaluation["modes"], "logical_split": "test_v2", "tuning_allowed": False,
                "similarity_threshold": settings.RETRIEVAL_VECTOR_MIN_USEFUL_SCORE,
                "rrf_k": settings.RETRIEVAL_RRF_K, "reranker_enabled": settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
                "physical_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
                "namespace": "task25b_r1_canary",
            },
            dataset_version="task25b-r1-v2", run_status="succeeded",
            started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc),
            metrics_json={"by_mode": evaluation["by_mode"], "quality_gate": gate, "blind_run": True},
        )
        db.add(run)
        db.flush()
        for row in evaluation["rows"]:
            ranking = row["staged_metrics"]["ranking"]
            db.add(RetrievalEvaluationResult(
                run_id=run.id, case_id=case_map[row["case_id"]].id, retrieval_mode=row["mode"],
                ranked_document_ids=[], ranked_chunk_ids=row["final_ranked"], ranked_media_ids=[],
                score_breakdown_json={"staged_metrics": row["staged_metrics"], "routing_reason": row["routing_reason"]},
                recall_at_5=ranking["recall_at_5"], recall_at_10=ranking["recall_at_10"],
                reciprocal_rank=ranking["mrr"], ndcg_at_10=ranking["ndcg_at_10"],
                precision_at_5=ranking["precision_at_5"], latency_ms=row["total_latency_ms"],
                fallback_used=row["fallback_used"], passed=row["error"] is None, error_summary=row["error"],
            ))
        for item in case_map.values():
            item.metadata_json = {**(item.metadata_json or {}), "blind_runs_completed": 1}
            db.add(item)
        db.commit()
        return str(run.id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.dataset != "test_v2":
        raise RuntimeError("the formal blind command requires --allow-real-api --dataset test_v2")
    if STARTED.exists() or RESULT.exists():
        raise RuntimeError("formal test_v2 blind run has already started or completed; rerun is forbidden")
    manifest = json.loads(FROZEN_MANIFEST.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN_LABELS.read_text(encoding="utf-8"))
    if manifest.get("formal_blind_runs_completed") != 0:
        raise RuntimeError("frozen manifest already records a blind run")
    current_hash = _current_label_hash()
    expected_hash = manifest["test_v2_frozen_hash"]
    if current_hash != expected_hash or frozen.get("labels_sha256") != expected_hash:
        raise RuntimeError("test_v2 frozen label hash mismatch")
    expected_ids = {
        str(value) for item in frozen["labels"]
        for key in ("expected_document_ids", "expected_chunk_ids", "expected_media_ids")
        for value in item.get(key, [])
    }
    leakage_scan = _label_leakage_scan(expected_ids)
    if not leakage_scan["passed"]:
        raise RuntimeError("test_v2 expected IDs were found in retrieval or tuning source files")
    write_json("blind_run_started.json", {
        "status": "STARTED", "started_at": now_iso(), "dataset": "test_v2",
        "frozen_hash": expected_hash, "formal_run_number": 1, "rerun_allowed": False,
    })
    evaluation = evaluate_split(
        split="test_v2", modes=["keyword", "vector", "hybrid", "hybrid_rerank", "adaptive"], allow_blind=True
    )
    keyword = evaluation["by_mode"]["keyword"]
    final = evaluation["by_mode"]["adaptive"]
    checks = {
        "frozen_hash": current_hash == expected_hash,
        "label_leakage": leakage_scan["passed"],
        "controlled_active_chunks": json.loads((RUNTIME / "corpus_seed.json").read_text(encoding="utf-8"))["active_chunks"] >= 160,
        "union_candidate_recall_at_50": final["union_candidate_recall_at_50"] >= 0.98,
        "recall_at_5": final["recall_at_5"] >= 0.85,
        "recall_at_10": final["recall_at_10"] >= 0.95,
        "mrr": final["mrr"] >= 0.80,
        "ndcg_at_10": final["ndcg_at_10"] >= 0.85,
        "citation_validity": final["citation_validity"] >= 0.98,
        "model_exact_accuracy": final["model_exact_accuracy"] == 1.0,
        "fault_code_exact_accuracy": final["fault_code_exact_accuracy"] == 1.0,
        "leakage": final["leakage"] == 0,
        "no_answer_f1": final["no_answer_f1"] >= 0.90,
        "no_answer_false_positive_rate": final["no_answer_false_positive_rate"] <= 0.05,
        "per_category_recall_at_5": final["per_category_minimum_recall_at_5"] >= 0.75,
        "warm_p95": final["latency_p95_ms"] <= 3500,
        "error_rate": final["error_rate"] == 0,
        "relative_mrr": final["mrr"] >= keyword["mrr"] - 0.01,
        "relative_ndcg": final["ndcg_at_10"] >= keyword["ndcg_at_10"] - 0.01,
        "reranker_effective_or_disabled": not get_settings().RETRIEVAL_FEATURE_RERANK_ENABLED,
        "collection_reconciliation": json.loads((RUNTIME / "collection_reconciliation.json").read_text(encoding="utf-8"))["status"] == "PASSED",
    }
    gate = {"passed": all(checks.values()), "checks": checks}
    run_id = _persist_run(evaluation, gate)
    payload = {
        "status": "PASSED" if gate["passed"] else "FAILED", "completed_at": now_iso(),
        "dataset": "test_v2", "dataset_version": "task25b-r1-v2", "formal_blind_run_number": 1,
        "rerun_allowed": False, "frozen_hash": expected_hash, "label_leakage_scan": leakage_scan,
        "evaluation_run_id": run_id, "evaluation": evaluation, "quality_gate": gate,
        "test_v2_used_for_tuning": False, "post_blind_tuning_allowed": False,
    }
    result_path = write_json("blind_quality_gate.json", payload)
    manifest["formal_blind_runs_completed"] = 1
    manifest["formal_blind_result_sha256"] = sha256_file(result_path)
    FROZEN_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_json("test_v2_result_hash.json", {
        "status": "FROZEN_RESULT", "dataset_frozen_hash": expected_hash,
        "blind_result_sha256": sha256_file(result_path), "formal_blind_runs_completed": 1,
        "rerun_allowed": False,
    })
    return 0 if gate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
