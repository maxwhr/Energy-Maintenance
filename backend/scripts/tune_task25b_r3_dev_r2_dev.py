from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import RetrievalEvaluationCase
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from task25b_r3_dev_r2_common import OUT, V3_DATASET, now_iso
from task25b_r3_dev_r2_metrics import aggregate, metric_row


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); parser.add_argument("--limit", type=int, default=24); args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit real API approval required")
    with SessionLocal() as db:
        cases = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V3_DATASET,
            RetrievalEvaluationCase.dataset_split.in_(["train", "dev"]),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name).limit(args.limit)))
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        chunks = {str(item.id): item for item in db.scalars(select(__import__("app.models", fromlist=["KnowledgeChunk"]).KnowledgeChunk))}
        documents = {str(item.id): item for item in db.scalars(select(__import__("app.models", fromlist=["KnowledgeDocument"]).KnowledgeDocument))}
        rows_by_mode = {mode: [] for mode in ("keyword", "adaptive")}
        for case in cases:
            for mode in rows_by_mode:
                result = ScopedRetrievalEngine(db, scope=scope, allow_real_api=True).retrieve(RetrievalQueryRequest(
                    question=case.query_text, retrieval_mode=mode, enable_vector=mode != "keyword", top_k=5, vector_top_k=50,
                    scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID, **{key: value for key, value in (case.required_filters or {}).items() if value is not None},
                ))
                rows_by_mode[mode].append(metric_row(case=case, mode=mode, surfaced_ids=result.ranked_chunk_ids, diagnostics=result.diagnostics, chunks=chunks, documents=documents))
    payload = {"generated_at": now_iso(), "dataset": V3_DATASET, "splits_used": ["train", "dev"], "test_v3_used": False,
               "cases": len(cases), "configuration": {"same_section_max": 1, "same_document_max": 2, "raw_top_k": 10,
               "surfaced_top_k_max": 5, "score_threshold": 0.20, "margin_threshold": 0.16},
               "by_mode": {mode: aggregate(rows) for mode, rows in rows_by_mode.items()}, "quality_thresholds_lowered": False,
               "expected_labels_used_in_runtime_rules": False}
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "dev_tuning_snapshot.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "cases": len(cases), "test_v3_used": False, "by_mode": payload["by_mode"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
