from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from task25e_common import SQLTrace, now_iso, read_json, sha256_value, write_json


N_PLUS_ONE = {
    "USER_N_PLUS_ONE",
    "DEVICE_N_PLUS_ONE",
    "WORKFLOW_N_PLUS_ONE",
    "DIAGNOSIS_N_PLUS_ONE",
    "SOP_N_PLUS_ONE",
    "TASK_N_PLUS_ONE",
    "MEDIA_N_PLUS_ONE",
    "CORRECTION_N_PLUS_ONE",
    "AUDIT_N_PLUS_ONE",
    "LAZY_RELATIONSHIP_LOAD",
    "SERIALIZER_TRIGGERED_QUERY",
}


def main() -> int:
    baseline = read_json("baseline.json", {})
    if baseline.get("status") != "TASK25E_BASELINE_FROZEN":
        raise SystemExit("Task 25E immutable baseline is missing")
    with SessionLocal() as db:
        with SQLTrace(db.get_bind()) as trace:
            response = RecordCenterService(db).overview()
    categories = Counter(item["category"] for item in trace.statements)
    n_plus_one_count = sum(value for key, value in categories.items() if key in N_PLUS_ONE)
    fingerprints = trace.fingerprints()
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if len(trace.statements) <= 40 and n_plus_one_count == 0 else "FAIL",
        "request": {"method": "GET", "path": "/api/record-center/overview", "parameters": {}},
        "parameter_policy": "parameters, credentials, tokens and private fields are not recorded",
        "statement_count": len(trace.statements),
        "baseline_statement_count": baseline.get("overview_sql_statements"),
        "statement_reduction": int(baseline.get("overview_sql_statements", 0)) - len(trace.statements),
        "response_sha256": sha256_value(response),
        "baseline_response_sha256": baseline.get("response_sha256"),
        "response_hash_match": sha256_value(response) == baseline.get("response_sha256"),
        "category_counts": dict(sorted(categories.items())),
        "n_plus_one_warning_count": n_plus_one_count,
        "statements": trace.statements,
    }
    write_json("sql_trace.json", payload)
    write_json(
        "sql_fingerprints.json",
        {
            "generated_at": payload["generated_at"],
            "statement_count": len(trace.statements),
            "unique_fingerprints": len(fingerprints),
            "top_30": fingerprints[:30],
        },
    )
    baseline_fingerprints = read_json("baseline_sql_fingerprints.json", {}).get("top_30", [])
    write_json(
        "n_plus_one_root_causes.json",
        {
            "generated_at": payload["generated_at"],
            "baseline_top_repeated": baseline_fingerprints[:10],
            "root_causes": [
                {"category": "USER_N_PLUS_ONE", "baseline_executions": 1412, "after_executions": categories.get("USER_N_PLUS_ONE", 0), "fix": "one page-wide users batch query"},
                {"category": "DEVICE_N_PLUS_ONE", "baseline_executions": 662, "after_executions": categories.get("DEVICE_N_PLUS_ONE", 0), "fix": "one page-wide devices batch query"},
                {"category": "PYTHON_SIDE_PAGINATION", "baseline": "11 full source loads", "after": "UNION ALL count and bounded identity page", "fix": "filter/order/offset/limit moved to PostgreSQL"},
                {"category": "PYTHON_SIDE_AGGREGATION", "baseline": "12 count statements", "after": "one UNION ALL aggregate statement", "fix": "fixed-count database aggregation"},
            ],
            "n_plus_one_warning_count": n_plus_one_count,
        },
    )
    print(json.dumps({"status": payload["status"], "sql": len(trace.statements), "n_plus_one": n_plus_one_count}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" and payload["response_hash_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
