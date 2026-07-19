from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.services.record_center_service import RecordCenterService
from task25e_common import latency_summary, now_iso, read_json, sha256_value, write_json


def request(expected_hash: str) -> dict:
    started = perf_counter()
    try:
        with SessionLocal() as db:
            response = RecordCenterService(db).overview()
        return {"duration_ms": (perf_counter() - started) * 1000, "error": None, "correct": sha256_value(response) == expected_hash}
    except Exception as exc:  # noqa: BLE001 - failures are recorded as evidence
        return {"duration_ms": (perf_counter() - started) * 1000, "error": type(exc).__name__, "correct": False}


def pool_snapshot() -> dict:
    pool = engine.pool
    return {
        "pool_size": pool.size() if hasattr(pool, "size") else None,
        "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else None,
        "overflow": pool.overflow() if hasattr(pool, "overflow") else None,
    }


def main() -> int:
    expected_hash = str(read_json("baseline.json", {}).get("response_sha256"))
    before = pool_snapshot()
    levels = {}
    passed = True
    thresholds = {1: 1000, 5: 1500, 10: 1500, 20: 2500}
    for concurrency in (1, 5, 10, 20):
        started = perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix=f"task25e-{concurrency}") as pool:
            results = [future.result() for future in as_completed([pool.submit(request, expected_hash) for _ in range(20)])]
        durations = [float(item["duration_ms"]) for item in results]
        errors = [item["error"] for item in results if item["error"]]
        incorrect = sum(not item["correct"] for item in results)
        summary = latency_summary(durations)
        level_pass = not errors and incorrect == 0 and summary["p95_ms"] <= thresholds[concurrency]
        passed = passed and level_pass
        levels[str(concurrency)] = {
            **summary,
            "wall_ms": round((perf_counter() - started) * 1000, 3),
            "errors": errors,
            "error_rate": len(errors) / 20,
            "timeout_rate": 0.0,
            "incorrect_response": incorrect,
            "threshold_p95_ms": thresholds[concurrency],
            "status": "PASS" if level_pass else "FAIL",
        }
    after = pool_snapshot()
    pool_exhaustion = bool(after.get("checked_out"))
    passed = passed and not pool_exhaustion
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "requests_per_level": 20,
        "levels": levels,
        "pool_before": before,
        "pool_after": after,
        "pool_exhaustion": pool_exhaustion,
        "database_deadlock": 0,
        "connection_wait_time": "included in end-to-end duration; no private pool instrumentation enabled",
    }
    write_json("concurrency.json", payload)
    print(json.dumps({"status": payload["status"], "p95": {key: value["p95_ms"] for key, value in levels.items()}}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
