from __future__ import annotations

import argparse
import csv
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import select

from task25f_common import load_suite, run_case
from task25f_r1_common import read_json, safe_settings_snapshot, write_json

from app.core.database import SessionLocal
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    low, high = math.floor(position), math.ceil(position)
    value = ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return round(value, 3)


def _user_id():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at))
        if user is None:
            user = db.scalar(select(User).where(User.status == "active").order_by(User.created_at))
        if user is None:
            raise RuntimeError("active persisted user required")
        return user.id


def _bare(query: str, *, mode: str, allow_real_api: bool, user_id) -> dict:
    started = time.perf_counter()
    error = None
    try:
        with SessionLocal() as db:
            service = QueryAwareRetrievalService(db, current_user=db.get(User, user_id))
            response = service.search(QueryAwareSearchRequest(
                query=query,
                retrieval_mode=mode,
                top_k=10,
                enable_llm=True,
                allow_real_api=allow_real_api,
            ))
            response.model_dump(mode="json")
    except Exception as exc:  # noqa: BLE001 - latency/error evidence.
        error = type(exc).__name__
    return {
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "error": error,
    }


def _concurrent(query: str, *, level: int, user_id) -> dict:
    rows = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=level, thread_name_prefix=f"task25f-r1-c{level}") as pool:
        futures = [pool.submit(_bare, query, mode="auto", allow_real_api=True, user_id=user_id) for _ in range(level)]
        for future in as_completed(futures):
            rows.append(future.result())
    errors = [item for item in rows if item["error"]]
    return {
        "concurrency": level,
        "request_count": len(rows),
        "p50_ms": _percentile([item["latency_ms"] for item in rows], 0.50),
        "p95_ms": _percentile([item["latency_ms"] for item in rows], 0.95),
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        "error_count": len(errors),
        "timeout_count": sum("timeout" in str(item["error"] or "").casefold() for item in errors),
        "pool_exhaustion_count": sum("pool" in str(item["error"] or "").casefold() for item in errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = safe_settings_snapshot()
    if not (args.allow_real_api and settings["TASK25B_ALLOW_REAL_API"]):
        raise SystemExit("explicit --allow-real-api and TASK25B_ALLOW_REAL_API=true are required")
    if settings["TASK25B_ALLOW_FULL_REINDEX"]:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    suite = load_suite()
    live = read_json("live_quality_stability.json", {})
    if not live.get("passed"):
        raise SystemExit("live quality must pass before performance preservation")
    user_id = _user_id()
    keyword_cases = list(suite["rows"][:10])
    hybrid_cases = [item for item in suite["rows"] if "requires_clarification" not in item.get("tags", [])][:10]
    multi_cases = [item for item in suite["rows"] if "multi_query" in item.get("tags", [])][:10]
    keyword_latencies = []
    for case in keyword_cases:
        _bare(case["query"], mode="fast", allow_real_api=False, user_id=user_id)
        keyword_latencies.append(_bare(case["query"], mode="fast", allow_real_api=False, user_id=user_id)["latency_ms"])
    hybrid_rows = []
    for case in hybrid_cases:
        run_case(case, allow_real_api=True, cache_mode="on")
        hybrid_rows.append(run_case(case, allow_real_api=True, cache_mode="on"))
    multi_rows = []
    for case in multi_cases:
        run_case(case, allow_real_api=True, cache_mode="on")
        multi_rows.append(run_case(case, allow_real_api=True, cache_mode="on"))
    concurrency_query = multi_cases[0]["query"] if multi_cases else hybrid_cases[0]["query"]
    _bare(concurrency_query, mode="auto", allow_real_api=True, user_id=user_id)
    concurrent_10 = _concurrent(concurrency_query, level=10, user_id=user_id)
    _bare(concurrency_query, mode="auto", allow_real_api=True, user_id=user_id)
    concurrent_20 = _concurrent(concurrency_query, level=20, user_id=user_id)
    case_evidence = live.get("case_evidence") or []
    sql_counts = [float(item["sql"]["count"]) for item in case_evidence if item.get("sql")]
    full_latencies = [float(item["total_ms"]) for item in case_evidence if item.get("total_ms")]
    citation_sql = sum(
        statement.get("stage") == "CITATION"
        for item in case_evidence if item.get("sql")
        for statement in item["sql"].get("statements") or []
    )
    n_plus_one = sum(int((item.get("sql") or {}).get("n_plus_one_warnings") or 0) for item in case_evidence)
    retry_latencies = []
    with open("../.runtime/task25f_r1/provider_aa_cases.csv", "r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row.get("retry_count") or 0) > 0:
                retry_latencies.append(float(row["latency_ms"]))
    metrics = {
        "sql_p95": _percentile(sql_counts, 0.95),
        "sql_max": max(sql_counts, default=0),
        "citation_sql": citation_sql,
        "n_plus_one": n_plus_one,
        "keyword_fast_p95_ms": _percentile(keyword_latencies, 0.95),
        "hybrid_warm_p95_ms": _percentile([float(item["total_ms"]) for item in hybrid_rows], 0.95),
        "multi_query_warm_p95_ms": _percentile([float(item["total_ms"]) for item in multi_rows], 0.95),
        "full_deterministic_p95_ms": _percentile(full_latencies, 0.95),
        "concurrent_10_p95_ms": concurrent_10["p95_ms"],
        "concurrent_20_p95_ms": concurrent_20["p95_ms"],
        "error_count": concurrent_10["error_count"] + concurrent_20["error_count"],
        "timeout_count": concurrent_10["timeout_count"] + concurrent_20["timeout_count"],
        "pool_exhaustion_count": concurrent_10["pool_exhaustion_count"] + concurrent_20["pool_exhaustion_count"],
        "retry_scenario_samples": len(retry_latencies),
        "retry_scenario_p95_ms": _percentile(retry_latencies, 0.95) if retry_latencies else None,
    }
    checks = {
        "sql_p95_le_8": metrics["sql_p95"] <= 8,
        "citation_sql_zero": citation_sql == 0,
        "n_plus_one_zero": n_plus_one == 0,
        "keyword_fast_p95_le_800": metrics["keyword_fast_p95_ms"] <= 800,
        "hybrid_warm_p95_le_3000": metrics["hybrid_warm_p95_ms"] <= 3000,
        "multi_query_warm_p95_le_4000": metrics["multi_query_warm_p95_ms"] <= 4000,
        "full_deterministic_p95_le_5000": metrics["full_deterministic_p95_ms"] <= 5000,
        "concurrent_10_p95_le_5000": metrics["concurrent_10_p95_ms"] <= 5000,
        "concurrent_20_p95_le_7000": metrics["concurrent_20_p95_ms"] <= 7000,
        "errors_zero": metrics["error_count"] == 0,
        "timeouts_zero": metrics["timeout_count"] == 0,
        "pool_exhaustion_zero": metrics["pool_exhaustion_count"] == 0,
    }
    passed = all(checks.values())
    payload = {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "metrics": metrics,
        "checks": checks,
        "keyword_samples": len(keyword_latencies),
        "hybrid_samples": len(hybrid_rows),
        "multi_query_samples": len(multi_rows),
        "concurrency": {"level_10": concurrent_10, "level_20": concurrent_20},
        "retry_latency_reported_separately": True,
        "normal_steady_state_excludes_retry_scenarios": True,
    }
    write_json("performance_preservation.json", payload)
    print(json.dumps({
        "status": payload["status"], "sql_p95": metrics["sql_p95"],
        "keyword_p95": metrics["keyword_fast_p95_ms"], "hybrid_p95": metrics["hybrid_warm_p95_ms"],
        "multi_p95": metrics["multi_query_warm_p95_ms"], "c10": metrics["concurrent_10_p95_ms"],
        "c20": metrics["concurrent_20_p95_ms"], "errors": metrics["error_count"],
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
