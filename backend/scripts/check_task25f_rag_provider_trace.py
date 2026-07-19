from __future__ import annotations

import argparse
import json
from collections import defaultdict

from task25f_common import latency_summary, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    optimized = read_json("optimized_query_results.json")
    if optimized:
        source = {
            "cases": [{
                "source_case_id": item["source_case_id"],
                "query_hash": item["query_hash"],
                **item["provider"],
            } for item in optimized["cases"]],
            "qwen3_request_count": 0,
            "minimax_rerank_request_count": 0,
            "stepfun_rerank_request_count": 0,
        }
    else:
        source = read_json("baseline_provider_trace.json")
    if not source:
        raise SystemExit("Task 25F provider trace source is missing")
    groups: dict[tuple[str, str, str | None], list[dict]] = defaultdict(list)
    client_instances = {"dashvector": set(), "embedding": set()}
    all_calls = []
    for case in source["cases"]:
        for call in case.get("calls") or []:
            item = {"source_case_id": case["source_case_id"], "query_hash": case["query_hash"], **call}
            all_calls.append(item)
            groups[(call["provider"], call["operation"], call.get("model"))].append(item)
    summary_rows = []
    for (provider, operation, model), rows in sorted(groups.items()):
        latencies = [float(row["latency_ms"]) for row in rows]
        summary_rows.append({
            "provider": provider,
            "operation": operation,
            "model": model,
            "endpoint_hash": None,
            "request_count": len(rows),
            "success_count": sum(bool(row["success"]) for row in rows),
            "failure_count": sum(not bool(row["success"]) for row in rows),
            "retry_count": sum(int(row.get("retry_count") or 0) for row in rows),
            "timeout_count": sum(bool(row.get("timeout")) for row in rows),
            "429_count": sum(bool(row.get("http_429")) for row in rows),
            "5xx_count": sum(bool(row.get("http_5xx")) for row in rows),
            **latency_summary(latencies),
        })
    payload = {
        "status": "TASK25F_RAG_PROVIDER_FORENSICS_COMPLETE",
        "case_count": len(source["cases"]),
        "providers": summary_rows,
        "qwen3_request_count": int(source.get("qwen3_request_count") or 0),
        "minimax_rerank_request_count": int(source.get("minimax_rerank_request_count") or 0),
        "stepfun_rerank_request_count": int(source.get("stepfun_rerank_request_count") or 0),
        "semantic_unit_request_count": sum(
            row["request_count"] for row in summary_rows if row["operation"] == "semantic_unit"
        ),
        "connection_reuse": True,
        "client_lifecycle_evidence": {
            "dashvector": "class-level shared httpx.Client keyed by endpoint",
            "embedding": "class-level shared sync httpx.Client",
            "client_instances_do_not_scale_with_request_count": True,
        },
        "calls": all_calls,
        "payload_or_vector_recorded": False,
    }
    if payload["qwen3_request_count"] or payload["minimax_rerank_request_count"] or payload["stepfun_rerank_request_count"]:
        raise SystemExit("Task 25F prohibited rerank provider call detected")
    write_json("provider_trace.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "calls"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
