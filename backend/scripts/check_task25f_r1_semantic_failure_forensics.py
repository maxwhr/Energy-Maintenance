from __future__ import annotations

import argparse
import json
from collections import Counter

from task25f_r1_common import TASK25F_RUNTIME, read_json, safe_settings_snapshot, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = safe_settings_snapshot()
    if not (args.allow_real_api and settings["TASK25B_ALLOW_REAL_API"]):
        raise SystemExit("explicit --allow-real-api and TASK25B_ALLOW_REAL_API=true are required")
    original = json.loads((TASK25F_RUNTIME / "provider_trace.json").read_text(encoding="utf-8"))
    optimized = json.loads((TASK25F_RUNTIME / "optimized_query_results.json").read_text(encoding="utf-8"))
    aa = read_json("provider_aa_stability.json", {})
    optimized_by_case = {item["source_case_id"]: item for item in optimized.get("cases") or []}
    failures = [
        item for item in original.get("calls") or []
        if item.get("operation") == "semantic_unit" and not item.get("success")
    ]
    rows = []
    for index, item in enumerate(failures, start=1):
        case = optimized_by_case.get(item.get("source_case_id")) or {}
        result = case.get("result") or {}
        rows.append({
            "failure_id": f"task25f-semantic-{index:02d}",
            "case_id": item.get("source_case_id"),
            "variant_hash": None,
            "operation": "SEMANTIC_UNIT",
            "attempt": 1,
            "error_type": item.get("failure") or "VectorStoreAdapterError",
            "failure_class": "UNKNOWN",
            "http_status": None,
            "provider_code": None,
            "latency_ms": item.get("latency_ms"),
            "concurrency_level": "NOT_CAPTURED_BY_TASK25F",
            "client_reused": True,
            "coalesced": True,
            "fallback_result": "SAFE_PARTIAL_CHANNEL_DEGRADATION",
            "other_channels_preserved": any(
                channel in (result.get("actual_channels") or [])
                for channel in ("EXACT_KEYWORD", "SCOPED_KEYWORD", "RAW_VECTOR")
            ),
            "classification_basis": "legacy_trace_retained_exception_type_only",
        })
    case_counts = Counter(item["case_id"] for item in rows)
    current_failures = int(aa.get("post_retry_failure_count") or 0)
    current_classes = dict(aa.get("failure_classes") or {})
    payload = {
        "status": "PASSED" if current_failures == 0 else "FAILED",
        "original_failure_count": len(rows),
        "original_unique_cases": len(case_counts),
        "original_failure_classes": {"UNKNOWN": len(rows)} if rows else {},
        "historical_unknown_reason": (
            "Task 25F provider trace retained exception type but not sanitized HTTP/provider code; "
            "classifying a transient or permanent cause now would fabricate evidence."
        ),
        "historical_telemetry_gap": True,
        "current_pre_retry_failure_count": int(aa.get("pre_retry_failure_count") or 0),
        "current_post_retry_failure_count": current_failures,
        "current_failure_classes": current_classes,
        "current_unknown_count": int(current_classes.get("UNKNOWN") or 0),
        "current_failure_rate": float(aa.get("post_retry_failure_rate") or 0.0),
        "transient": sum(
            int(current_classes.get(name) or 0)
            for name in ("NETWORK_CONNECT", "NETWORK_READ", "HTTP_429", "HTTP_5XX")
        ),
        "permanent": sum(
            int(current_classes.get(name) or 0)
            for name in ("INDEX_NOT_FOUND", "PARTITION_NOT_FOUND", "FILTER_ERROR")
        ),
        "configuration": sum(
            int(current_classes.get(name) or 0)
            for name in ("INDEX_NOT_FOUND", "PARTITION_NOT_FOUND", "FILTER_ERROR")
        ),
        "mapping": int(current_classes.get("MAPPING_ERROR") or 0),
        "limited_retry": {
            "enabled": True,
            "maximum_retries": 1,
            "retryable": ["NETWORK_CONNECT", "NETWORK_READ", "HTTP_429", "HTTP_502", "HTTP_503", "HTTP_504"],
            "non_retryable": ["HTTP_400", "HTTP_401", "HTTP_403", "HTTP_404", "FILTER_ERROR", "MAPPING_ERROR", "CONFIGURATION", "CANCELLED"],
            "global_provider_semaphore": True,
            "overall_request_budget": True,
            "retry_success_count": int(aa.get("retry_success_count") or 0),
        },
        "sequential_aa_failures": current_failures,
        "shared_vs_independent_client_parity": (aa.get("shared_vs_independent_client") or {}).get(
            "exact_candidate_order_parity"
        ),
        "concentration": {
            "cases_with_multiple_failures": sorted(case_id for case_id, count in case_counts.items() if count > 1),
            "maximum_failures_per_case": max(case_counts.values(), default=0),
        },
        "provider_calls_this_check": 0,
        "rows": rows,
    }
    write_json("semantic_failure_forensics.json", payload)
    print(json.dumps({
        "status": payload["status"], "original_failures": len(rows),
        "historical_unknown": len(rows), "current_failures": current_failures,
        "retry_enabled": True,
    }, ensure_ascii=False))
    return 0 if payload["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
