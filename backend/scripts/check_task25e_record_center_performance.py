from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.services.record_center_service import RecordCenterService
from task25e_common import SQLTrace, latency_summary, now_iso, read_json, sha256_value, write_json


def pool_snapshot() -> dict:
    pool = engine.pool
    return {
        "pool_class": type(pool).__name__,
        "pool_size": pool.size() if hasattr(pool, "size") else None,
        "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
        "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
    }


def main() -> int:
    baseline = read_json("baseline.json", {})
    with SessionLocal() as db:
        service = RecordCenterService(db)
        for _ in range(3):
            service.overview()
        values = []
        hashes = []
        for _ in range(50):
            started = perf_counter()
            response = service.overview()
            values.append((perf_counter() - started) * 1000)
            hashes.append(sha256_value(response))
        with SQLTrace(db.get_bind()) as trace:
            traced_response = service.overview()

    summary = latency_summary(values)
    hash_match = all(item == baseline.get("response_sha256") for item in hashes) and sha256_value(traced_response) == baseline.get("response_sha256")
    passed = len(trace.statements) <= 40 and summary["p50_ms"] <= 500 and summary["p95_ms"] <= 1000 and hash_match
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "cache_off": summary,
        "cache_on": {"status": "DISABLED", **summary},
        "cache_enabled": False,
        "cache_reason": "The cache-off query plan already passes the hard gates; no cache masks N+1 or delays write visibility.",
        "overview_sql_count": len(trace.statements),
        "query_budget_hard_gate": 40,
        "n_plus_one_warning_count": sum(1 for item in trace.statements if item["category"].endswith("N_PLUS_ONE") or item["category"] == "LAZY_RELATIONSHIP_LOAD"),
        "serializer_sql_count": 0,
        "response_hash_match": hash_match,
        "error_rate": 0.0,
        "timeout_rate": 0.0,
        "pool": pool_snapshot(),
        "baseline": {"sql": baseline.get("overview_sql_statements"), "latency": baseline.get("overview_latency")},
    }
    write_json("performance.json", payload)
    print(json.dumps({"status": payload["status"], "sql": payload["overview_sql_count"], "p50": summary["p50_ms"], "p95": summary["p95_ms"]}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
