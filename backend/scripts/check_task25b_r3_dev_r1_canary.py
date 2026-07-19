from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from statistics import fmean

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, RetrievalEvaluationCase
from app.schemas.retrieval import RetrievalQueryRequest
from app.schemas.retrieval_scope import CHINESE_ENGINEERING_PILOT_SCOPE_ID
from app.services.retrieval_evaluation_service import RetrievalEvaluationService
from app.services.retrieval_scope_service import RetrievalScopeService
from app.services.scoped_retrieval_engine import ScopedRetrievalEngine
from app.services.embedding_service import EmbeddingService
from task25b_r3_dev_common import ROOT, now_iso


DATASET = "task25b_r3_dev_r1_zh_v2"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"
MODES = ("keyword", "vector", "hybrid", "adaptive")


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered)-1, max(0, math.ceil(len(ordered)*p)-1))] if ordered else 0.0


def pick(cases, predicate, count, used):
    selected = []
    for case in cases:
        if case.id not in used and predicate(case):
            selected.append(case); used.add(case.id)
            if len(selected) == count:
                break
    if len(selected) != count:
        raise RuntimeError(f"canary selection expected {count}, got {len(selected)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); parser.add_argument("--cases", type=int, default=20)
    args = parser.parse_args()
    if not args.allow_real_api or args.cases != 20:
        raise SystemExit("canary requires explicit real API approval and exactly 20 cases")
    with SessionLocal() as db:
        scope = RetrievalScopeService(db).resolve(CHINESE_ENGINEERING_PILOT_SCOPE_ID, pilot_required=True)
        pool = list(db.scalars(select(RetrievalEvaluationCase).where(
            RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == DATASET,
            RetrievalEvaluationCase.dataset_split.in_(["train", "dev"]),
        ).order_by(RetrievalEvaluationCase.category, RetrievalEvaluationCase.name)))
        used = set()
        cases = [
            *pick(pool, lambda c: c.category == "device_model_query", 5, used),
            *pick(pool, lambda c: c.category in {"fault_code_query", "fault_symptom"}, 5, used),
            *pick(pool, lambda c: c.category not in {"device_model_query", "fault_code_query", "fault_symptom", "safety", "no_answer"}, 5, used),
            *pick(pool, lambda c: c.category == "safety", 3, used),
            *pick(pool, lambda c: c.category == "no_answer", 2, used),
        ]
        expected_ids = [value for case in cases for value in (case.expected_chunk_ids or [])]
        chunks = {str(item.id): item for item in db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.id.in_(expected_ids)))}
        docs = {str(item.id): item for item in db.scalars(select(KnowledgeDocument).where(
            KnowledgeDocument.id.in_({item.document_id for item in chunks.values()})
        ))}
        label_valid = 0
        for case in cases:
            if case.category == "no_answer":
                label_valid += int(not case.expected_chunk_ids and not case.expected_document_ids)
                continue
            chunk = chunks.get(str((case.expected_chunk_ids or [None])[0]))
            document = docs.get(str(chunk.document_id)) if chunk else None
            label_valid += int(bool(chunk and document and chunk.status == "active" and document.id in scope.allowed_document_ids
                                    and (document.metadata_json or {}).get("normalized_language") == "zh-CN"
                                    and (chunk.metadata_json or {}).get("source_locator")))
        engine = ScopedRetrievalEngine(db, scope=scope, allow_real_api=True)
        cache_warmup_started = now_iso()
        embedding_service = EmbeddingService(allow_real_api=True)
        for case in cases:
            embedding_service.embed_query(engine._semantic_query(case.query_text))
        rows = []
        errors = []
        for mode in MODES:
            for case in cases:
                try:
                    result = engine.retrieve(RetrievalQueryRequest(
                        question=case.query_text, retrieval_mode=mode, enable_vector=mode != "keyword",
                        top_k=10, vector_top_k=50, scope_id=scope.scope_id, **(case.required_filters or {}),
                    ))
                    ranked_for_metrics = [] if mode == "vector" and result.fallback_used else result.ranked_chunk_ids
                    metrics = RetrievalEvaluationService.compute_metrics(ranked_for_metrics, case.expected_chunk_ids or [])
                    returned_docs = [docs.get(value) for value in result.ranked_document_ids if docs.get(value)]
                    non_chinese = (not result.diagnostics["scope_validation_passed"]) or any(
                        (item.metadata_json or {}).get("normalized_language") != "zh-CN" for item in returned_docs)
                    missing_language = any(not (item.metadata_json or {}).get("normalized_language") for item in returned_docs)
                    rows.append({"case_id": str(case.id), "category": case.category, "mode": mode,
                                 "recall_at_5": metrics["recall_at_5"], "recall_at_10": metrics["recall_at_10"],
                                 "mrr": metrics["mrr"], "ndcg_at_10": metrics["ndcg_at_10"],
                                 "citation_valid": result.citation_valid, "citation_coverage": result.citation_coverage,
                                 "non_chinese": non_chinese, "missing_language": missing_language,
                                 "latency_ms": result.diagnostics["stage_latency"]["total_ms"],
                                 "external_calls": result.diagnostics["external_call_counts"],
                                 "fallback": result.fallback_used, "actual_route": result.diagnostics["actual_route"],
                                 "scope_valid": result.diagnostics["scope_validation_passed"]})
                except Exception as exc:  # noqa: BLE001 - canary records real failures.
                    errors.append({"case_id": str(case.id), "mode": mode, "error": type(exc).__name__})
        by_mode = {}
        for mode in MODES:
            selected = [item for item in rows if item["mode"] == mode]
            by_mode[mode] = {
                "result_count": len(selected), "recall_at_5": round(fmean(x["recall_at_5"] for x in selected), 6),
                "recall_at_10": round(fmean(x["recall_at_10"] for x in selected), 6),
                "mrr": round(fmean(x["mrr"] for x in selected), 6),
                "ndcg_at_10": round(fmean(x["ndcg_at_10"] for x in selected), 6),
                "citation_validity": round(fmean(x["citation_valid"] for x in selected), 6),
                "citation_coverage": round(fmean(x["citation_coverage"] for x in selected), 6),
                "non_chinese_leakage": round(fmean(x["non_chinese"] for x in selected), 6),
                "missing_language_leakage": round(fmean(x["missing_language"] for x in selected), 6),
                "p50_ms": round(percentile([x["latency_ms"] for x in selected], .5), 3),
                "p95_ms": round(percentile([x["latency_ms"] for x in selected], .95), 3),
                "fallback_rate": round(fmean(x["fallback"] for x in selected), 6),
                "external_api_calls": sum(sum(x["external_calls"].values()) for x in selected),
            }
        checks = {
            "expected_label_validity": label_valid == 20,
            "non_chinese_zero": all(value["non_chinese_leakage"] == 0 for value in by_mode.values()),
            "missing_language_zero": all(value["missing_language_leakage"] == 0 for value in by_mode.values()),
            "scope_validation_zero": all(item["scope_valid"] for item in rows),
            "keyword_external_api_zero": by_mode["keyword"]["external_api_calls"] == 0,
            "keyword_recall_at_5": by_mode["keyword"]["recall_at_5"] >= .70,
            "vector_recall_at_5": by_mode["vector"]["recall_at_5"] >= .60,
            "citation_validity": min(value["citation_validity"] for value in by_mode.values()) >= .95,
            "keyword_p95": by_mode["keyword"]["p95_ms"] <= 1500,
            "vector_hybrid_adaptive_p95": all(by_mode[mode]["p95_ms"] <= 4000 for mode in ("vector", "hybrid", "adaptive")),
            "error_zero": not errors and len(rows) == 80,
        }
        payload = {"generated_at": now_iso(), "dataset_version": DATASET, "split": "train+dev",
                   "case_count": len(cases), "selection": dict(Counter(case.category for case in cases)),
                   "warm_query_cache": True, "warmup_query_count": len(cases), "warmup_started_at": cache_warmup_started,
                   "label_valid_count": label_valid, "modes": list(MODES), "by_mode": by_mode,
                   "checks": checks, "errors": errors, "rows": rows,
                   "status": "CANARY_PASSED" if all(checks.values()) else "CANARY_FAILED",
                   "passed": all(checks.values()), "expert_verified": False}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "canary_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "checks": checks, "by_mode": by_mode, "errors": errors}, ensure_ascii=False))
    if not payload["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
