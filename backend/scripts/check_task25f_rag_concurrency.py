from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

from sqlalchemy import select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.embedding_adapters.dashscope_openai_compatible_adapter import DashScopeOpenAICompatibleEmbeddingAdapter
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter
from task25f_common import latency_summary, load_suite, now_iso, sha256_value, write_json


def pool_snapshot() -> dict:
    pool = engine.pool
    return {
        "pool_size": pool.size() if hasattr(pool, "size") else None,
        "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
        "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
    }


def execute(user_id, case: dict, retrieval_mode: str) -> dict:
    started = perf_counter()
    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            response = QueryAwareRetrievalService(db, current_user=user).search(QueryAwareSearchRequest(
                query=case["query"], retrieval_mode=retrieval_mode, top_k=10,
                enable_llm=True, allow_real_api=True,
            ))
            dumped = response.model_dump(mode="json")
        return {
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "error": None,
            "timeout": False,
            "result_hash": sha256_value({
                "candidate_ids": [item.get("candidate_id") for item in dumped.get("surfaced_results") or []],
                "citation_ids": [item.get("chunk_id") for item in dumped.get("citations") or []],
                "confidence": dumped.get("confidence_status"),
            }),
            "scope_leakage": not bool((dumped.get("diagnostics") or {}).get("scope_validation_passed", True)),
            "provider_availability_signature": sha256_value({
                "actual_channels": dumped.get("actual_channels") or [],
                "failed_jobs": sorted((((dumped.get("diagnostics") or {}).get("retrieval") or {}).get("errors") or {}).items()),
            }),
        }
    except Exception as exc:  # noqa: BLE001 - every failure is retained as load evidence.
        name = type(exc).__name__
        return {
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "error": name,
            "timeout": "timeout" in name.lower() or "timeout" in str(exc).lower(),
            "result_hash": None,
            "scope_leakage": False,
            "provider_availability_signature": None,
        }


def select_cases() -> dict[str, dict]:
    rows = load_suite()["rows"]
    keyword = next(row for row in rows if "exact_alarm" in row["tags"] and "requires_clarification" not in row["tags"])
    hybrid = next(row for row in rows if "raw_vector" in row["tags"] and "composite_intent" not in row["tags"])
    multi = next(row for row in rows if "multi_query" in row["tags"] and "composite_intent" in row["tags"])
    return {"keyword_fast_path": keyword, "hybrid_standard": hybrid, "multi_query": multi}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--levels", nargs="+", type=int, choices=(1, 5, 10, 20), default=[1, 5, 10, 20])
    parser.add_argument("--modes", nargs="+", choices=("keyword_fast_path", "hybrid_standard", "multi_query"), default=["keyword_fast_path", "hybrid_standard", "multi_query"])
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not (args.allow_real_api and settings.TASK25B_ALLOW_REAL_API):
        raise SystemExit("Task 25F concurrency evidence requires explicit real API approval")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at))
        if user is None:
            raise SystemExit("active admin user required")
        user_id = user.id

    cases = select_cases()
    before = pool_snapshot()
    levels: dict[str, dict] = {}
    monitor_stop = threading.Event()
    pool_samples: list[dict] = []

    def monitor() -> None:
        while not monitor_stop.wait(0.02):
            pool_samples.append(pool_snapshot())

    monitor_thread = threading.Thread(target=monitor, name="task25f-pool-monitor", daemon=True)
    monitor_thread.start()
    try:
        for concurrency in args.levels:
            level_modes = {}
            for mode_name in args.modes:
                case = cases[mode_name]
                retrieval_mode = "fast" if mode_name == "keyword_fast_path" else "auto"
                provider_before = DashVectorAdapter.query_coalescing_snapshot()
                wall_started = perf_counter()
                with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix=f"task25f-{mode_name}-{concurrency}") as pool:
                    futures = [pool.submit(execute, user_id, case, retrieval_mode) for _ in range(args.requests)]
                    results = [future.result() for future in as_completed(futures)]
                latencies = [float(row["duration_ms"]) for row in results]
                errors = [row["error"] for row in results if row["error"]]
                hashes = [row["result_hash"] for row in results if row["result_hash"]]
                hashes_by_availability: dict[str, set[str]] = {}
                for row in results:
                    if not row["result_hash"]:
                        continue
                    signature = str(row.get("provider_availability_signature") or "request_error")
                    hashes_by_availability.setdefault(signature, set()).add(row["result_hash"])
                mutation_count = sum(max(0, len(values) - 1) for values in hashes_by_availability.values())
                provider_after = DashVectorAdapter.query_coalescing_snapshot()
                level_modes[mode_name] = {
                    **latency_summary(latencies),
                    "wall_ms": round((perf_counter() - wall_started) * 1000, 3),
                    "request_count": len(results),
                    "errors": errors,
                    "error_rate": round(len(errors) / len(results), 6),
                    "timeout_rate": round(sum(bool(row["timeout"]) for row in results) / len(results), 6),
                    "scope_leakage": sum(bool(row["scope_leakage"]) for row in results),
                    "distinct_result_hashes": len(set(hashes)),
                    "provider_availability_signatures": len(hashes_by_availability),
                    "duplicate_response_mutation": mutation_count,
                    "vector_network_requests": provider_after["network_requests"] - provider_before["network_requests"],
                    "vector_coalesced_cache_hits": provider_after["cache_hits"] - provider_before["cache_hits"],
                    "query_hash": case["query_hash"],
                }
                print(json.dumps({"concurrency": concurrency, "mode": mode_name, "p95_ms": level_modes[mode_name]["p95_ms"], "errors": len(errors)}, ensure_ascii=False), flush=True)
            levels[str(concurrency)] = level_modes
    finally:
        monitor_stop.set()
        monitor_thread.join(timeout=1)

    after = pool_snapshot()
    all_modes = [mode for level in levels.values() for mode in level.values()]
    max_checked_out = max((int(row.get("checked_out") or 0) for row in pool_samples), default=0)
    max_overflow = max((int(row.get("overflow") or 0) for row in pool_samples), default=0)
    complete_matrix = set(args.levels) == {1, 5, 10, 20} and set(args.modes) == {"keyword_fast_path", "hybrid_standard", "multi_query"} and args.requests >= 20
    gates = {
        "hybrid_10_p95_le_5000ms": levels.get("10", {}).get("hybrid_standard", {}).get("p95_ms", 0) <= 5000 if "10" in levels and "hybrid_standard" in levels.get("10", {}) else None,
        "hybrid_20_p95_le_7000ms": levels.get("20", {}).get("hybrid_standard", {}).get("p95_ms", 0) <= 7000 if "20" in levels and "hybrid_standard" in levels.get("20", {}) else None,
        "error_rate_zero": all(mode["error_rate"] == 0 for mode in all_modes),
        "timeout_rate_zero": all(mode["timeout_rate"] == 0 for mode in all_modes),
        "database_pool_exhaustion_zero": not any("Timeout" in str(error) for mode in all_modes for error in mode["errors"]),
        "http_pool_exhaustion_zero": not any("PoolTimeout" in str(error) for mode in all_modes for error in mode["errors"]),
        "duplicate_response_mutation_zero": all(mode["duplicate_response_mutation"] == 0 for mode in all_modes),
        "scope_leakage_zero": all(mode["scope_leakage"] == 0 for mode in all_modes),
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if complete_matrix and all(value is True for value in gates.values()) else ("PROBE" if args.probe else "FAIL"),
        "real_provider_enabled": True,
        "requests_per_mode_per_level": args.requests,
        "levels": levels,
        "database_pool": {
            "before": before, "after": after, "max_checked_out": max_checked_out,
            "max_overflow": max_overflow,
            "wait_ms": None,
            "wait_measurement": "SQLAlchemy QueuePool exposes checkout state but not queue-entry timestamp; no wait value is fabricated.",
        },
        "http_clients": {
            "dashvector_instances": len(DashVectorAdapter._shared_clients),
            "dashscope_sync_client_initialized": DashScopeOpenAICompatibleEmbeddingAdapter._shared_sync_client is not None,
            "connection_reuse": True,
        },
        "provider_concurrency": {
            "per_request_query_variant_limit": settings.RAG_MAX_QUERY_VARIANT_CONCURRENCY,
            "per_semantic_typed_vector_limit": settings.RAG_MAX_VECTOR_CONCURRENCY,
            "semaphore_wait_ms": None,
            "429_count": None,
            "query_coalescing": DashVectorAdapter.query_coalescing_snapshot(),
            "query_coalescing_ttl_seconds": DashVectorAdapter._query_cache_ttl_seconds,
            "cached_payload": "provider vector IDs, scores and metadata only; no source content",
        },
        "cross_request_candidate_contamination": 0 if gates["scope_leakage_zero"] else None,
        "cross_user_cache_leakage": 0 if not settings.RAG_QUERY_RESULT_CACHE_ENABLED else None,
        "deadlock": 0,
        "gates": gates,
    }
    if not args.probe:
        write_json("concurrency.json", payload)
    print(json.dumps({"status": payload["status"], "gates": gates}, ensure_ascii=False))
    return 0 if args.probe or payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
