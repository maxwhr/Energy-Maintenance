from __future__ import annotations

import json
import math
from statistics import fmean

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from task25b_r3_dev_common import ROOT, now_iso


DATASET = "task25b_r3_dev_r1_zh_v2"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def percentile(values: list[float], p: float) -> float:
    values = sorted(values); return values[min(len(values)-1, max(0, math.ceil(len(values)*p)-1))] if values else 0.0


def main() -> None:
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split.in_(["train", "dev"]),
            RetrievalEvaluationCase.category != "no_answer",
        ).order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.created_at).limit(30)))
        engine = ScopedRetrievalEngine(db, scope=scope, allow_real_api=False)
        rows = []
        for case in cases:
            request = RetrievalQueryRequest(question=case.query_text, retrieval_mode="keyword", enable_vector=False,
                                            top_k=10, scope_id=scope.scope_id, **(case.required_filters or {}))
            result = engine.retrieve(request)
            metrics = RetrievalEvaluationService.compute_metrics(result.ranked_chunk_ids, case.expected_chunk_ids or [])
            diagnostics = result.diagnostics
            rows.append({"case_id": str(case.id), "recall_at_5": metrics["recall_at_5"],
                         "mrr": metrics["mrr"], "citation_valid": result.citation_valid,
                         "latency_ms": diagnostics["stage_latency"]["total_ms"],
                         "external_calls": sum(diagnostics["external_call_counts"].values()),
                         "embedding_ms": diagnostics["stage_latency"]["embedding_ms"],
                         "dashvector_ms": diagnostics["stage_latency"]["dashvector_ms"],
                         "scope_valid": diagnostics["scope_validation_passed"]})
        payload = {"generated_at": now_iso(), "cases": len(rows),
                   "recall_at_5": round(fmean(item["recall_at_5"] for item in rows), 6),
                   "mrr": round(fmean(item["mrr"] for item in rows), 6),
                   "citation_validity": round(fmean(item["citation_valid"] for item in rows), 6),
                   "p50_ms": round(percentile([item["latency_ms"] for item in rows], .5), 3),
                   "p95_ms": round(percentile([item["latency_ms"] for item in rows], .95), 3),
                   "external_api_call_count": sum(item["external_calls"] for item in rows),
                   "embedding_violation_count": sum(item["embedding_ms"] > 0 for item in rows),
                   "dashvector_violation_count": sum(item["dashvector_ms"] > 0 for item in rows),
                   "scope_violation_count": sum(not item["scope_valid"] for item in rows), "rows": rows}
        payload["passed"] = payload["external_api_call_count"] == 0 and payload["embedding_violation_count"] == 0 \
            and payload["dashvector_violation_count"] == 0 and payload["scope_violation_count"] == 0
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "keyword_path.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
