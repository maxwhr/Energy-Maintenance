from __future__ import annotations

import json
from collections import defaultdict

from task25f_common import latency_summary, read_json, write_csv, write_json


def main() -> int:
    optimized = read_json("optimized_query_results.json")
    if optimized:
        source = {
            "cases": [{
                "source_case_id": item["source_case_id"],
                "query_hash": item["query_hash"],
                "total_ms": item["total_ms"],
                "stage_latency": item["result"]["stage_latency"],
            } for item in optimized["cases"]]
        }
        source_name = "optimized_query_results.json"
    else:
        source = read_json("baseline_stage_latency.json")
        source_name = "baseline_stage_latency.json"
    if not source:
        raise SystemExit("Task 25F stage trace source is missing")
    stage_values: dict[str, list[float]] = defaultdict(list)
    csv_rows = []
    for case in source["cases"]:
        row = {
            "source_case_id": case["source_case_id"],
            "query_hash": case["query_hash"],
            "total_ms": case["total_ms"],
        }
        for key, value in (case.get("stage_latency") or {}).items():
            stage_values[key].append(float(value or 0.0))
            row[key] = value
        csv_rows.append(row)
    summary = {key: latency_summary(values) for key, values in sorted(stage_values.items())}
    payload = {
        "status": "TASK25F_RAG_STAGE_TRACE_COMPLETE",
        "source": source_name,
        "case_count": len(csv_rows),
        "query_text_recorded": False,
        "stage_summary": summary,
        "cases": source["cases"],
    }
    write_json("stage_trace.json", payload)
    fields = ["source_case_id", "query_hash", "total_ms", *sorted(stage_values)]
    write_csv("stage_trace_cases.csv", csv_rows, fields)
    print(json.dumps({"status": payload["status"], "case_count": payload["case_count"], "total": summary.get("total_ms")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
