from __future__ import annotations

import argparse
import json
from collections import Counter

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from task25b_r3_dev_r2_common import MODES, OUT, V3_DATASET, now_iso
from task25b_r3_dev_r2_metrics import aggregate, metric_row, vector_heavy


def _take(cases, predicate, count, selected):
    values = [case for case in cases if predicate(case) and case.id not in {item.id for item in selected}]
    selected.extend(values[:count])


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); parser.add_argument("--cases", type=int, default=24); args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit real API approval required")
    if args.cases != 24:
        raise SystemExit("R2 canary is fixed at 24 stratified train/dev cases")
    with SessionLocal() as db:
        pool = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == V3_DATASET,
            RetrievalEvaluationCase.dataset_split.in_(["train", "dev"]),
        ).order_by(RetrievalEvaluationCase.dataset_split, RetrievalEvaluationCase.name)))
        selected = []
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_model_case")), 4, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_alarm_case")), 4, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_vector_heavy")), 6, selected)
        _take(pool, lambda case: int((case.metadata_json or {}).get("relevance_cardinality") or 0) > 1, 4, selected)
        _take(pool, lambda case: int((case.metadata_json or {}).get("relevance_cardinality") or 0) == 1, 3, selected)
        _take(pool, lambda case: bool((case.metadata_json or {}).get("is_no_answer")), 3, selected)
        if len(selected) != 24:
            raise SystemExit(f"stratified canary incomplete: {len(selected)}/24")
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        chunks = {str(item.id): item for item in db.scalars(select(KnowledgeChunk))}; documents = {str(item.id): item for item in db.scalars(select(KnowledgeDocument))}
        rows_by_mode = {mode: [] for mode in MODES}; errors = []
        for case in selected:
            for mode in MODES:
                try:
                    result = ScopedRetrievalEngine(db, scope=scope, allow_real_api=True).retrieve(RetrievalQueryRequest(
                        question=case.query_text, retrieval_mode=mode, enable_vector=mode != "keyword", top_k=5, vector_top_k=50,
                        scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID, **{key: value for key, value in (case.required_filters or {}).items() if value is not None},
                    ))
                    rows_by_mode[mode].append(metric_row(case=case, mode=mode, surfaced_ids=result.ranked_chunk_ids, diagnostics=result.diagnostics, chunks=chunks, documents=documents))
                except Exception as exc:  # noqa: BLE001
                    errors.append({"case_id": str(case.id), "mode": mode, "error": type(exc).__name__})
        by_mode = {mode: aggregate(rows) for mode, rows in rows_by_mode.items()}; heavy = vector_heavy(rows_by_mode)
        labels_valid = all(bool(case.expected_chunk_ids or case.expected_document_ids) != bool((case.metadata_json or {}).get("is_no_answer")) for case in selected)
        checks = {
            "label_validity": labels_valid, "coverage": len(selected) == 24,
            "no_leakage": all(metrics["leakage"] == 0 for metrics in by_mode.values()),
            "keyword_external_zero": sum(sum(row["external_calls"].values()) for row in rows_by_mode["keyword"]) == 0,
            "keyword_recall_at_5": by_mode["keyword"]["recall_at_5"] >= .70,
            "vector_recall_at_5": by_mode["vector"]["recall_at_5"] >= .60,
            "citation_validity": all(metrics["citation_validity"] >= .95 for metrics in by_mode.values()),
            "keyword_p95": by_mode["keyword"]["p95_ms"] <= 1500,
            "vector_hybrid_adaptive_p95": all(by_mode[mode]["p95_ms"] <= 4000 for mode in ("vector", "hybrid", "adaptive")),
            "error_zero": not errors,
            "adaptive_vector_heavy_route": sum(heavy["adaptive_routes"].get(route, 0) for route in ("vector", "hybrid", "hybrid_rerank")) >= 1,
            "mode_not_all_identical": any(row["raw_ids"] != counterpart["raw_ids"] for row, counterpart in zip(rows_by_mode["keyword"], rows_by_mode["vector"])),
            "vector_heavy_gain": heavy["relative_recall_gain"] >= .10 or heavy["relative_ndcg_gain"] >= .08,
        }
        payload = {"generated_at": now_iso(), "dataset": V3_DATASET, "split": "train+dev", "formal_test_v3_used": False,
                   "cases": len(selected), "category_counts": dict(Counter(case.category for case in selected)), "by_mode": by_mode,
                   "vector_heavy": heavy, "checks": checks, "errors": errors, "rows": [row for rows in rows_by_mode.values() for row in rows],
                   "status": "CANARY_PASSED" if all(checks.values()) else "CANARY_FAILED", "passed": all(checks.values())}
    OUT.mkdir(parents=True, exist_ok=True)
    previous = OUT / "canary_result.json"
    if previous.exists():
        attempt = 1
        while (OUT / f"canary_attempt_{attempt}.json").exists():
            attempt += 1
        (OUT / f"canary_attempt_{attempt}.json").write_bytes(previous.read_bytes())
    (OUT / "canary_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "checks": checks, "by_mode": by_mode, "vector_heavy": heavy}, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
