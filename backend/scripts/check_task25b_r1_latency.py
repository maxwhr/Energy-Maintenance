from __future__ import annotations

import argparse
import statistics
import time

from sqlalchemy import select

from task25b_r1_common import now_iso, write_json
from task25b_r1_eval_common import CANARY_NAMESPACE, load_cases, percentile
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.retrieval import RetrievalQueryRequest
from app.services.embedding_service import EmbeddingService
from app.services.retrieval_service import RetrievalService


def _measure(db, user, cases, label: str) -> list[dict]:
    settings = get_settings()
    rows = []
    for case in cases:
        started = time.perf_counter()
        response = RetrievalService(
            db, allow_real_api=True, vector_collection=settings.DASHVECTOR_PHYSICAL_COLLECTION,
            vector_namespace=CANARY_NAMESPACE,
        ).query(RetrievalQueryRequest(
            question=case.query_text, retrieval_mode="adaptive", enable_vector=True,
            top_k=10, vector_top_k=50, include_history=False, enable_kg_enhancement=False,
            **(case.required_filters or {}),
        ), user)
        breakdown = response.retrieval_diagnostics.get("latency_breakdown_ms") or {}
        rows.append({
            "case_id": str(case.id), "phase": label,
            "total_latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "stage_latency_ms": breakdown,
            "cache_hit": bool(breakdown.get("query_embedding_cache_hit")),
            "fallback_used": response.fallback_used, "fallback_reason": response.fallback_reason,
        })
    return rows


def _summary(rows: list[dict]) -> dict:
    values = [float(item["total_latency_ms"]) for item in rows]
    return {
        "p50_ms": round(percentile(values, .50), 3), "p95_ms": round(percentile(values, .95), 3),
        "p99_ms": round(percentile(values, .99), 3),
        "cache_hit_rate": round(statistics.fmean(float(item["cache_hit"]) for item in rows), 6),
        "fallback_rate": round(statistics.fmean(float(item["fallback_used"]) for item in rows), 6),
        "stage_mean_ms": {
            key: round(statistics.fmean(float(item["stage_latency_ms"].get(key) or 0) for item in rows), 3)
            for key in ("query_understanding", "keyword_retrieval", "query_embedding", "dashvector_query",
                        "postgresql_validation", "fusion", "rerank", "citation_validation", "total")
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise RuntimeError("--allow-real-api is required")
    with EmbeddingService._cache_lock:
        EmbeddingService._query_cache.clear()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        cases = [item for item in load_cases(db, "dev") if item.category in {
            "fault_symptom_query", "image_ocr_query", "image_visual_descriptor_query", "similar_history_case"
        }][:16]
        cold = _measure(db, user, cases, "cold")
        warm = _measure(db, user, cases, "warm")
    payload = {
        "status": "PASSED" if _summary(warm)["p95_ms"] <= 3500 else "FAILED",
        "generated_at": now_iso(), "case_count": len(cases), "cold": _summary(cold), "warm": _summary(warm),
        "rows": [*cold, *warm], "total_budget_ms": get_settings().RETRIEVAL_TOTAL_BUDGET_MS,
        "external_concurrency_max": get_settings().EMBEDDING_MAX_CONCURRENCY,
        "final_ranked_result_cached": False, "permission_result_cached": False,
        "document_status_cached": False, "test_v2_labels_read": False,
    }
    write_json("latency.json", payload)
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

