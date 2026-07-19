from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from task25b_r1_common import ROOT, now_iso, sha256_file, sha256_text, write_csv, write_json
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun


SOURCE_ARTIFACT = ROOT / ".runtime" / "task25b" / "retrieval_evaluation.json"


def main() -> int:
    source = json.loads(SOURCE_ARTIFACT.read_text(encoding="utf-8"))
    run_id = source.get("run_id")
    if not run_id:
        raise RuntimeError("Task 25B retrieval artifact has no run_id")

    with SessionLocal() as db:
        run = db.get(RetrievalEvaluationRun, run_id)
        if run is None:
            raise RuntimeError("Task 25B retrieval run is missing from PostgreSQL")
        results = list(db.scalars(
            select(RetrievalEvaluationResult)
            .where(RetrievalEvaluationResult.run_id == run.id)
            .order_by(RetrievalEvaluationResult.case_id, RetrievalEvaluationResult.retrieval_mode)
        ))
        case_ids = {item.case_id for item in results}
        cases = {
            item.id: item
            for item in db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.id.in_(case_ids)))
        }

        rows = []
        for result in results:
            case = cases[result.case_id]
            rows.append({
                "run_id": str(run.id),
                "case_id": str(case.id),
                "case_name": case.name,
                "category": case.category,
                "dataset_split": case.dataset_split,
                "query_sha256": sha256_text(case.query_text),
                "expected_document_ids": case.expected_document_ids or [],
                "expected_chunk_ids": case.expected_chunk_ids or [],
                "expected_media_ids": case.expected_media_ids or [],
                "retrieval_mode": result.retrieval_mode,
                "ranked_document_ids": result.ranked_document_ids or [],
                "ranked_chunk_ids": result.ranked_chunk_ids or [],
                "ranked_media_ids": result.ranked_media_ids or [],
                "score_breakdown": result.score_breakdown_json or {},
                "recall_at_5": result.recall_at_5,
                "recall_at_10": result.recall_at_10,
                "reciprocal_rank": result.reciprocal_rank,
                "ndcg_at_10": result.ndcg_at_10,
                "precision_at_5": result.precision_at_5,
                "latency_ms": result.latency_ms,
                "fallback_used": result.fallback_used,
                "passed": result.passed,
                "error_summary": result.error_summary,
            })

        snapshot = {
            "status": "FROZEN",
            "frozen_at": now_iso(),
            "purpose": "Task 25B exposed test_v1; error analysis and regression only",
            "independent_final_test_allowed": False,
            "source_artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)),
            "source_artifact_sha256": sha256_file(SOURCE_ARTIFACT),
            "run": {
                "id": str(run.id),
                "name": run.name,
                "dataset_version": run.dataset_version,
                "run_status": run.run_status,
                "embedding_provider": run.embedding_provider,
                "embedding_model": run.embedding_model,
                "embedding_dimension": run.embedding_dimension,
                "vector_backend": run.vector_backend,
                "collection_name": run.collection_name,
                "retrieval_config": run.retrieval_config_json or {},
                "metrics": run.metrics_json or {},
                "started_at": run.started_at,
                "completed_at": run.completed_at,
            },
            "case_count": len(case_ids),
            "result_count": len(rows),
            "case_results": rows,
        }

    snapshot_path = write_json("task25b_v1_frozen_snapshot.json", snapshot)
    fieldnames = [
        "run_id", "case_id", "case_name", "category", "dataset_split", "query_sha256",
        "expected_document_ids", "expected_chunk_ids", "expected_media_ids", "retrieval_mode",
        "ranked_document_ids", "ranked_chunk_ids", "ranked_media_ids", "score_breakdown",
        "recall_at_5", "recall_at_10", "reciprocal_rank", "ndcg_at_10", "precision_at_5",
        "latency_ms", "fallback_used", "passed", "error_summary",
    ]
    csv_path = write_csv("task25b_v1_case_results.csv", fieldnames, rows)
    manifest = {
        "status": "FROZEN",
        "generated_at": now_iso(),
        "dataset_version": snapshot["run"]["dataset_version"],
        "run_id": snapshot["run"]["id"],
        "case_count": snapshot["case_count"],
        "result_count": snapshot["result_count"],
        "artifacts": {
            str(SOURCE_ARTIFACT.relative_to(ROOT)): sha256_file(SOURCE_ARTIFACT),
            str(snapshot_path.relative_to(ROOT)): sha256_file(snapshot_path),
            str(csv_path.relative_to(ROOT)): sha256_file(csv_path),
        },
    }
    write_json("task25b_v1_hash_manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
