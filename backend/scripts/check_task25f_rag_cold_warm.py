from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from sqlalchemy import select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.embedding_adapters.dashscope_openai_compatible_adapter import DashScopeOpenAICompatibleEmbeddingAdapter
from app.services.embedding_service import EmbeddingService
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter
from task25f_common import latency_summary, load_suite, now_iso, sha256_value, write_json


def select_case() -> dict:
    return next(
        row for row in load_suite()["rows"]
        if "raw_vector" in row["tags"] and "composite_intent" not in row["tags"]
    )


def user_id():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at))
        if user is None:
            raise RuntimeError("active admin user required")
        return user.id


def request_once(actor_id, case: dict) -> dict:
    before_embedding_client = DashScopeOpenAICompatibleEmbeddingAdapter._shared_sync_client is not None
    before_vector_clients = len(DashVectorAdapter._shared_clients)
    started = perf_counter()
    with SessionLocal() as db:
        response = QueryAwareRetrievalService(db, current_user=db.get(User, actor_id)).search(QueryAwareSearchRequest(
            query=case["query"], retrieval_mode="auto", top_k=10,
            enable_llm=True, allow_real_api=True,
        ))
        dumped = response.model_dump(mode="json")
    return {
        "duration_ms": round((perf_counter() - started) * 1000, 3),
        "result_hash": sha256_value({
            "candidate_ids": [item.get("candidate_id") for item in dumped.get("surfaced_results") or []],
            "citation_ids": [item.get("chunk_id") for item in dumped.get("citations") or []],
            "confidence": dumped.get("confidence_status"),
        }),
        "client_initialization": {
            "embedding_created": not before_embedding_client and DashScopeOpenAICompatibleEmbeddingAdapter._shared_sync_client is not None,
            "dashvector_clients_created": len(DashVectorAdapter._shared_clients) - before_vector_clients,
        },
        "stage_latency": dumped.get("stage_latency") or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--restart-probe", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not (args.allow_real_api and settings.TASK25B_ALLOW_REAL_API):
        raise SystemExit("Task 25F cold/warm evidence requires explicit real API approval")
    case = select_case()
    actor_id = user_id()
    if args.restart_probe:
        with EmbeddingService._cache_lock:
            EmbeddingService._query_cache.clear()
        print(json.dumps(request_once(actor_id, case), ensure_ascii=False))
        return 0

    with EmbeddingService._cache_lock:
        EmbeddingService._query_cache.clear()
    first = request_once(actor_id, case)
    second = request_once(actor_id, case)
    steady = []
    for index in range(50):
        item = request_once(actor_id, case)
        steady.append(item)
        if (index + 1) % 10 == 0:
            print(json.dumps({"steady_progress": index + 1, "duration_ms": item["duration_ms"]}), flush=True)

    child = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--allow-real-api", "--restart-probe"],
        cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, check=False,
    )
    restart = None
    if child.returncode == 0:
        for line in reversed(child.stdout.splitlines()):
            try:
                restart = json.loads(line)
                break
            except ValueError:
                continue
    steady_summary = latency_summary([float(item["duration_ms"]) for item in steady])
    result_hashes = [first["result_hash"], second["result_hash"], *(item["result_hash"] for item in steady)]
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if restart and len(set(result_hashes)) == 1 else "FAIL",
        "real_provider_enabled": True,
        "query_hash": case["query_hash"],
        "process_first_request": first,
        "second_request": second,
        "steady_50": steady_summary,
        "steady_distinct_result_hashes": len(set(item["result_hash"] for item in steady)),
        "service_restart_first_request": restart,
        "service_restart_probe_exit_code": child.returncode,
        "first_request_penalty_ms": round(first["duration_ms"] - steady_summary["p50_ms"], 3),
        "observability": {
            "client_initialization": "measured by shared-client before/after state",
            "dns_tls_ms": None,
            "database_connection_ms": None,
            "cache_cold_warm": "embedding request cache explicitly cleared before first and restart probes",
            "metadata_load_ms": first["stage_latency"].get("keyword_ms"),
            "unavailable_fields_reason": "Provider clients do not expose separate DNS/TLS timing and SQLAlchemy does not expose connection establishment timing without invasive hooks; no values are fabricated.",
        },
        "startup_paid_api_prewarm": False,
        "startup_full_corpus_load": False,
    }
    write_json("cold_warm.json", payload)
    print(json.dumps({"status": payload["status"], "first_ms": first["duration_ms"], "second_ms": second["duration_ms"], "steady_p95_ms": steady_summary["p95_ms"], "restart_ms": (restart or {}).get("duration_ms")}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
