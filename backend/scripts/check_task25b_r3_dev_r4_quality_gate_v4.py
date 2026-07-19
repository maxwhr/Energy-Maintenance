from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, RetrievalDatasetFreeze, RetrievalEvaluationCase, RetrievalEvaluationRun, User
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from check_task25b_r3_dev_r4_canary import metrics, run_chunk_mode, run_grounded
from task25b_r3_dev_r4_common import COLLECTION, OUT, now_iso, read_json, write_json


DATASET = "task25b_r3_dev_r4_zh_v4"
FREEZE = "task25b_r3_dev_r4_zh_v4_test_v4"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.dataset != "test_v4":
        raise SystemExit("only the explicit frozen test_v4 quality gate is permitted")
    canary = read_json(OUT / "canary_iteration_2.json") or read_json(OUT / "canary_iteration_1.json")
    if not canary.get("passed"):
        raise SystemExit("formal v4 quality gate blocked: Grounded Canary has not passed")
    if (OUT / "quality_gate_v4.json").exists():
        raise SystemExit("the single formal test_v4 run has already been recorded")
    tuning = read_json(OUT / "dev_tuning.json")
    with SessionLocal() as db:
        freeze = db.scalar(select(RetrievalDatasetFreeze).where(
            RetrievalDatasetFreeze.dataset_version == FREEZE, RetrievalDatasetFreeze.freeze_status == "frozen",
        ))
        if freeze is None:
            raise SystemExit("frozen test_v4 is required")
        prior = int(db.scalar(select(func.count()).select_from(RetrievalEvaluationRun).where(
            RetrievalEvaluationRun.dataset_version == FREEZE
        )) or 0)
        if prior:
            raise SystemExit("formal test_v4 run count is already non-zero")
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split == "test_v4",
        ).order_by(RetrievalEvaluationCase.name)))
        if len(cases) != 60:
            raise SystemExit(f"expected 60 frozen test_v4 cases, got {len(cases)}")
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
        if admin is None:
            raise SystemExit("admin actor required")
        run = RetrievalEvaluationRun(
            name="task25b_r3_dev_r4_formal_quality_gate_v4", embedding_provider="dashscope_openai_compatible",
            embedding_model="text-embedding-v4", embedding_dimension=1024, vector_backend="dashvector",
            collection_name=COLLECTION, retrieval_config_json={
                "raw_partition": "pilot_r2", "grounded_partition": "pilot_r4_grounded",
                "default_partition_changed": False, "full_reindex": False,
            }, dataset_version=FREEZE, run_status="running", started_at=datetime.now(timezone.utc), created_by=admin.id,
        )
        db.add(run); db.commit(); db.refresh(run)
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk))}
        # Warm the immutable formal cases once; only the following rows are scored.
        run_chunk_mode("raw_vector_pilot_r2", cases, db, scope, chunks)
        run_grounded(cases, db, scope, tuning)
        rows = {
            "keyword": run_chunk_mode("keyword", cases, db, scope, chunks),
            "raw_vector_pilot_r2": run_chunk_mode("raw_vector_pilot_r2", cases, db, scope, chunks),
        }
        grounded, adaptive = run_grounded(cases, db, scope, tuning)
        rows["grounded_semantic_unit"] = grounded; rows["adaptive_grounded"] = adaptive
        by_mode = {
            mode: metrics(mode_rows, expected_key="expected_semantic_unit_id" if "grounded" in mode else "expected_chunk_id")
            for mode, mode_rows in rows.items()
        }
        heavy = {mode: [row for row in mode_rows if row["vector_heavy"]] for mode, mode_rows in rows.items()}
        heavy_metrics = {
            mode: metrics(mode_rows, expected_key="expected_semantic_unit_id" if "grounded" in mode else "expected_chunk_id")
            for mode, mode_rows in heavy.items()
        }
        candidate_recall = sum(row["candidate_hit_at_50"] for row in heavy["grounded_semantic_unit"]) / len(heavy["grounded_semantic_unit"])
        adaptive_rows = rows["adaptive_grounded"]
        answer = [row for row in adaptive_rows if not row["no_answer"]]
        no_answer = [row for row in adaptive_rows if row["no_answer"]]
        surfaced_precision = sum(row["expected_semantic_unit_id"] in row["ranked_ids"][:5] for row in answer) / max(1, sum(bool(row["ranked_ids"]) for row in answer))
        citation_validity = sum(row["citation_valid"] for row in answer) / len(answer)
        citation_coverage = sum(row["citation_valid"] and bool(row["ranked_ids"]) for row in answer) / len(answer)
        no_answer_precision = sum(not row["ranked_ids"] for row in no_answer) / len(no_answer) if no_answer else 0.0
        no_answer_f1 = 2 * no_answer_precision / (1 + no_answer_precision) if no_answer_precision else 0.0
        adaptive = by_mode["adaptive_grounded"]
        checks = {
            "hit_at_5": adaptive["recall_at_5"] >= 0.90, "recall_at_10": adaptive["recall_at_10"] >= 0.90,
            "mrr": adaptive["mrr"] >= 0.80, "ndcg_at_10": adaptive["ndcg_at_10"] >= 0.85,
            "surfaced_precision": surfaced_precision >= 0.70, "citation_validity": citation_validity >= 0.98,
            "citation_coverage": citation_coverage >= 0.95, "no_answer_f1": no_answer_f1 >= 0.85,
            "leakage_zero": adaptive["leakage"] == 0, "error_zero": adaptive["errors"] == 0,
            "warm_p95": adaptive["warm_p95_ms"] <= 3500,
            "vector_candidate_recall": candidate_recall >= 0.90,
            "vector_grounded_recall_5": heavy_metrics["grounded_semantic_unit"]["recall_at_5"] >= 0.80,
            "vector_adaptive_recall_5": heavy_metrics["adaptive_grounded"]["recall_at_5"] >= 0.85,
            "vector_adaptive_mrr": heavy_metrics["adaptive_grounded"]["mrr"] >= 0.75,
            "vector_adaptive_ndcg": heavy_metrics["adaptive_grounded"]["ndcg_at_10"] >= 0.80,
            "global_not_below_keyword_over_1pct": adaptive["recall_at_5"] + 0.01 >= by_mode["keyword"]["recall_at_5"],
        }
        payload = {
            "generated_at": now_iso(), "dataset": FREEZE, "frozen": True, "run_count": 1,
            "run_id": str(run.id), "by_mode": by_mode,
            "vector_heavy": {"candidate_recall_at_50": round(candidate_recall, 6), **heavy_metrics},
            "derived": {"surfaced_precision": round(surfaced_precision, 6),
                        "citation_validity": round(citation_validity, 6), "citation_coverage": round(citation_coverage, 6),
                        "no_answer_f1": round(no_answer_f1, 6)},
            "checks": checks, "passed": all(checks.values()),
            "status": "QUALITY_GATE_PASSED" if all(checks.values()) else "QUALITY_GATE_FAILED",
            "expert_verified": False, "full_reindex": False,
        }
        run.metrics_json = payload; run.run_status = "completed"; run.completed_at = datetime.now(timezone.utc)
        db.commit()
    write_json("quality_gate_v4.json", payload)
    print({"status": payload["status"], "run_count": 1, "checks": checks})
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
