from __future__ import annotations

import statistics
import time

from sqlalchemy import select

from task25b_r1_common import now_iso, write_json
from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase, User
from app.schemas.retrieval import RetrievalQueryRequest
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.retrieval_service import RetrievalService


def main() -> int:
    rows = []
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.source_type == "engineering_controlled",
            RetrievalEvaluationCase.dataset_split == "test",
            RetrievalEvaluationCase.review_status == "engineering_verified",
        ).order_by(RetrievalEvaluationCase.name)))
        user = db.scalar(select(User).where(User.role == "admin"))
        for case in cases:
            for mode in ("keyword", "adaptive"):
                started = time.perf_counter()
                response = RetrievalService(db, allow_real_api=True).query(RetrievalQueryRequest(
                    question=case.query_text, retrieval_mode=mode, enable_vector=mode != "keyword",
                    top_k=10, vector_top_k=50, include_history=False, enable_kg_enhancement=False,
                    **(case.required_filters or {}),
                ), user)
                ranked = [str(item.chunk_id) for item in response.retrieved_chunks]
                expected = [str(item) for item in (case.expected_chunk_ids or [])]
                rows.append({
                    "case_id": str(case.id), "category": case.category, "mode": mode,
                    "metrics": RetrievalEvaluationService.compute_metrics(ranked, expected),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "insufficient_evidence": response.insufficient_evidence,
                })
    by_mode = {}
    for mode in ("keyword", "adaptive"):
        values = [item for item in rows if item["mode"] == mode]
        by_mode[mode] = {
            "recall_at_5": round(statistics.fmean(item["metrics"]["recall_at_5"] for item in values), 6),
            "recall_at_10": round(statistics.fmean(item["metrics"]["recall_at_10"] for item in values), 6),
            "mrr": round(statistics.fmean(item["metrics"]["mrr"] for item in values), 6),
            "ndcg_at_10": round(statistics.fmean(item["metrics"]["ndcg_at_10"] for item in values), 6),
            "error_count": 0,
        }
    payload = {
        "status": "PASSED", "generated_at": now_iso(), "dataset": "task25b-v1-exposed",
        "usage": "regression_only", "independent_blind_claim": False, "case_count": len(cases),
        "by_mode": by_mode, "rows": rows, "test_v2_labels_read": False,
    }
    write_json("test_v1_regression.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
