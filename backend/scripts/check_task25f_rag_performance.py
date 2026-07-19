from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from task25f_common import latency_summary, now_iso, read_json, write_json


def _summarize(rows: list[dict]) -> dict:
    return latency_summary([float(row["total_ms"]) for row in rows])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--cache-mode", choices=("off", "on"), required=True)
    args = parser.parse_args()
    settings = get_settings()
    if not (args.allow_real_api and settings.TASK25B_ALLOW_REAL_API):
        raise SystemExit("Task 25F performance evidence requires explicit real API approval")

    measured = read_json("optimized_query_results.json", {})
    rows = list(measured.get("cases") or [])
    if len(rows) != 60:
        raise SystemExit("optimized 60-case measurement is missing")

    if args.cache_mode == "on" and not settings.RAG_QUERY_RESULT_CACHE_ENABLED:
        payload = {
            "generated_at": now_iso(),
            "status": "TASK25F_CACHE_NOT_ENABLED",
            "cache_mode": "on",
            "measurement_status": "NOT_APPLICABLE_CACHE_DISABLED",
            "reason": "No permission-safe result cache was required by the measured root cause; no cache-on result is fabricated.",
            "cache_feature_enabled": False,
            "reference_cache_off": (read_json("performance_cache_off.json", {}) or {}).get("metrics"),
        }
        write_json("performance_cache_on.json", payload)
        print(json.dumps({"status": payload["status"], "measurement_status": payload["measurement_status"]}))
        return 0

    keyword_rows = [
        row for row in rows
        if int((row.get("provider") or {}).get("request_count") or 0) == 0
        and ({"exact_model", "exact_alarm"} & set(row.get("tags") or []))
    ]
    hybrid_rows = [row for row in rows if int((row.get("provider") or {}).get("request_count") or 0) > 0]
    multi_rows = [row for row in rows if len((row.get("result") or {}).get("query_variants") or []) >= 3]
    all_summary = _summarize(rows)
    mode_metrics = {
        "keyword_fast_path": _summarize(keyword_rows),
        "hybrid_standard": _summarize(hybrid_rows),
        "multi_query": _summarize(multi_rows),
        "deterministic_complete": all_summary,
    }
    gates = {
        "keyword_fast_path_p95_le_800ms": mode_metrics["keyword_fast_path"]["p95_ms"] <= 800,
        "hybrid_standard_p95_le_3000ms": mode_metrics["hybrid_standard"]["p95_ms"] <= 3000,
        "multi_query_p95_le_4000ms": mode_metrics["multi_query"]["p95_ms"] <= 4000,
        "deterministic_path_p95_le_5000ms": all_summary["p95_ms"] <= 5000,
        "legacy_6000ms_gate": all_summary["p95_ms"] <= 6000,
        "error_rate_zero": not any(row.get("error") for row in rows),
        "timeout_rate_zero": not any("timeout" in str(row.get("error") or "").lower() for row in rows),
    }
    baseline_p95 = float((((read_json("baseline.json", {}) or {}).get("metrics") or {}).get("total_latency") or {}).get("p95_ms") or 0)
    improvement = round((baseline_p95 - all_summary["p95_ms"]) / baseline_p95, 6) if baseline_p95 else None
    hard_gate_passed = all(gates.values())
    payload = {
        "generated_at": now_iso(),
        "status": "TASK25F_CACHE_OFF_MEASURED" if hard_gate_passed else "TASK25F_RAG_PERFORMANCE_FAILED",
        "cache_mode": args.cache_mode,
        "cache_feature_enabled": bool(settings.RAG_QUERY_RESULT_CACHE_ENABLED),
        "dataset_version": measured.get("dataset_version"),
        "cases": len(rows),
        "mode_classification": {
            "keyword_fast_path": "provider_request_count=0 and an exact model/alarm suite tag",
            "hybrid_standard": "at least one measured embedding/vector provider request",
            "multi_query": "three or more generated query variants",
        },
        "mode_metrics": mode_metrics,
        "baseline_p95_ms": baseline_p95,
        "optimized_p95_ms": all_summary["p95_ms"],
        "improvement_ratio": improvement,
        "gates": gates,
        "hard_gate_passed": hard_gate_passed,
        "network_outliers_reported_separately": True,
    }
    write_json("performance_cache_off.json", payload)
    print(json.dumps({"status": payload["status"], "p95_ms": all_summary["p95_ms"], "gates": gates}, ensure_ascii=False))
    return 0 if hard_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
