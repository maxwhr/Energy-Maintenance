from __future__ import annotations

import argparse
import json
from uuid import UUID

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalDatasetFreeze, RetrievalEvaluationCase, RetrievalEvaluationResult, RetrievalEvaluationRun, User
from app.schemas.retrieval_evaluation import RetrievalEvaluationRequest
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from task25b_r3_dev_r2_common import MODES, OUT, V3_DATASET, V3_FREEZE, V3_PURPOSE, now_iso
from task25b_r3_dev_r2_metrics import aggregate, metric_row, vector_heavy


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); parser.add_argument("--dataset", required=True, choices=["test_v3"]); args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit real API approval required")
    canary = json.loads((OUT / "canary_result.json").read_text(encoding="utf-8"))
    if not canary.get("passed"):
        raise SystemExit("formal v3 evaluation forbidden: CANARY_FAILED")
    with SessionLocal() as db:
        freeze = db.scalar(select(RetrievalDatasetFreeze).where(RetrievalDatasetFreeze.dataset_version == V3_FREEZE, RetrievalDatasetFreeze.freeze_status == "frozen"))
        if freeze is None:
            raise SystemExit("test_v3 is not frozen")
        existing = db.scalar(select(RetrievalEvaluationRun).where(RetrievalEvaluationRun.name == V3_PURPOSE))
        if existing is not None:
            raise SystemExit(f"formal test_v3 run already exists: {existing.id}")
        admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
        run_data = RetrievalEvaluationService(db).evaluate(RetrievalEvaluationRequest(name=V3_PURPOSE, dataset_split="test_v3", modes=list(MODES), max_cases=60, dataset_version=V3_DATASET), admin)
        run = db.get(RetrievalEvaluationRun, UUID(str(run_data["id"])))
        cases = {case.id: case for case in db.scalars(select(RetrievalEvaluationCase).where(RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V3_DATASET, RetrievalEvaluationCase.dataset_split == "test_v3"))}
        results = list(db.scalars(select(RetrievalEvaluationResult).where(RetrievalEvaluationResult.run_id == run.id)))
        chunk_ids = {UUID(str(value)) for result in results for value in (result.ranked_chunk_ids or [])}
        chunk_ids.update(UUID(str(value)) for case in cases.values() for value in (case.expected_chunk_ids or []))
        chunks = {str(chunk.id): chunk for chunk in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids)))}
        docs = {str(doc.id): doc for doc in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_({chunk.document_id for chunk in chunks.values()})))}
        rows_by_mode = {mode: [] for mode in MODES}
        for result in results:
            diagnostics = (result.score_breakdown_json or {}).get("_diagnostics") or {}
            rows_by_mode[result.retrieval_mode].append(metric_row(case=cases[result.case_id], mode=result.retrieval_mode,
                surfaced_ids=[str(value) for value in (result.ranked_chunk_ids or [])], diagnostics=diagnostics, chunks=chunks, documents=docs, error=bool(result.error_summary)))
    by_mode = {mode: aggregate(rows) for mode, rows in rows_by_mode.items()}; heavy = vector_heavy(rows_by_mode); adaptive, keyword = by_mode["adaptive"], by_mode["keyword"]
    checks = {"hit_at_5": adaptive["hit_at_5"] >= .90, "recall_at_10": adaptive["recall_at_10"] >= .90, "mrr": adaptive["mrr"] >= .80,
              "ndcg": adaptive["ndcg_at_10"] >= .85, "citation_validity": adaptive["citation_validity"] >= .98, "citation_coverage": adaptive["citation_coverage"] >= .95,
              "surfaced_precision": adaptive["surfaced_precision"] >= .70, "surfaced_irrelevant_rate": adaptive["surfaced_irrelevant_rate"] <= .30,
              "no_answer": adaptive["no_answer_f1"] >= .85, "leakage": all(values["leakage"] == 0 for values in by_mode.values()), "error": all(values["error_rate"] == 0 for values in by_mode.values()),
              "keyword_p95": keyword["p95_ms"] <= 1000, "vector_p95": all(by_mode[mode]["p95_ms"] <= 3500 for mode in ("vector", "hybrid", "adaptive")),
              "multi_precision": adaptive["multi_relevant"]["precision_at_5"] >= .45, "multi_r_precision": adaptive["multi_relevant"]["r_precision"] >= .70,
              "model": adaptive["model"]["coverage"] >= 12 and adaptive["model"]["query_extraction"] >= .95 and adaptive["model"]["retrieved_consistency"] >= .95 and adaptive["model"]["exact_filter"] == 1.0,
              "alarm": adaptive["alarm"]["coverage"] >= 12 and adaptive["alarm"]["query_extraction"] >= .95 and adaptive["alarm"]["retrieved_consistency"] >= .95 and adaptive["alarm"]["exact_filter"] >= .95,
              "vector_candidate_recall": heavy["vector_candidate_recall_at_50"] >= .90, "vector_gain": heavy["relative_recall_gain"] >= .10 or heavy["relative_ndcg_gain"] >= .08}
    result = "DEVELOPMENT_ENGINEERING_PILOT_PASS" if all(checks.values()) else ("DEVELOPMENT_ENGINEERING_VECTOR_GAIN_NOT_PROVEN" if not checks["vector_gain"] else "DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED")
    payload = {"generated_at": now_iso(), "purpose": V3_PURPOSE, "run_id": str(run.id), "dataset": V3_DATASET, "freeze": V3_FREEZE,
               "cases": 60, "modes": list(MODES), "by_mode": by_mode, "vector_heavy": heavy, "checks": checks, "result": result,
               "expert_verified": False, "rows": [row for rows in rows_by_mode.values() for row in rows]}
    (OUT / "quality_gate_v3.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": result, "run_id": str(run.id), "checks": checks}, ensure_ascii=False))
    if result != "DEVELOPMENT_ENGINEERING_PILOT_PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
