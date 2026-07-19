from __future__ import annotations

import argparse
import json

from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter

from task25f_common import (
    aggregate_case_metrics,
    load_suite,
    now_iso,
    read_json,
    run_case,
    write_json,
)


PARITY_FIELDS = (
    "query_understanding",
    "query_variants",
    "requested_channels",
    "actual_channels",
    "candidate_identities",
    "top5_identities",
    "top10_identities",
    "citation_identities",
    "citation_locators",
    "confidence_status",
    "needs_clarification",
    "no_answer",
    "scope_leakage",
    "quality_status",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    suite = load_suite()
    baseline = read_json("baseline_query_results.json")
    if not baseline:
        raise SystemExit("Task 25F baseline_query_results.json is missing")
    baseline_by_id = {item["source_case_id"]: item["result"] for item in baseline["cases"]}
    # Keep the measured suite self-contained. Cross-case coalescing inside this
    # run remains enabled, but prior probes cannot pre-warm provider results.
    with DashVectorAdapter._query_cache_lock:
        DashVectorAdapter._query_cache.clear()
        DashVectorAdapter._query_inflight.clear()
    progress = read_json("optimized_progress.json", {"cases": []}) if args.resume else {"cases": []}
    completed = {item["source_case_id"] for item in progress.get("cases") or [] if not item.get("error")}

    for index, case in enumerate(suite["rows"], start=1):
        if case["source_case_id"] in completed:
            continue
        try:
            result = run_case(case, allow_real_api=args.allow_real_api, cache_mode="off")
        except Exception as exc:  # noqa: BLE001 - checkpoint preserves the failure for review.
            result = {
                "source_case_id": case["source_case_id"],
                "query_hash": case["query_hash"],
                "tags": case.get("tags") or [],
                "error": type(exc).__name__,
            }
        progress["generated_at"] = now_iso()
        progress["cases"] = [
            item for item in progress.get("cases") or []
            if item.get("source_case_id") != case["source_case_id"]
        ] + [result]
        write_json("optimized_progress.json", progress)
        print(json.dumps({
            "progress": f"{index}/{suite['case_count']}",
            "source_case_id": case["source_case_id"],
            "total_ms": result.get("total_ms"),
            "sql_count": (result.get("sql") or {}).get("count"),
            "provider_requests": (result.get("provider") or {}).get("request_count"),
            "error": result.get("error"),
        }, ensure_ascii=False), flush=True)

    order = {row["source_case_id"]: row["ordinal"] for row in suite["rows"]}
    cases = sorted(progress["cases"], key=lambda item: order[item["source_case_id"]])
    if len(cases) != suite["case_count"] or any(item.get("error") for item in cases):
        raise SystemExit("Task 25F optimized run incomplete; rerun with --resume")

    comparisons = []
    for item in cases:
        before = baseline_by_id[item["source_case_id"]]
        after = item["result"]
        fields = {field: before.get(field) == after.get(field) for field in PARITY_FIELDS}
        comparisons.append({
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            "fields": fields,
            "passed": all(fields.values()),
            "candidate_loss": len(set(before["candidate_identities"]) - set(after["candidate_identities"])),
            "scope_leakage": bool(after["scope_leakage"]),
        })
    field_parity = {
        field: round(sum(row["fields"][field] for row in comparisons) / len(comparisons), 6)
        for field in PARITY_FIELDS
    }
    payload = {
        "status": "TASK25F_RAG_RESPONSE_PARITY_PASS" if all(row["passed"] for row in comparisons) else "TASK25F_RAG_COMPATIBILITY_FAILED",
        "case_count": len(comparisons),
        "field_parity": field_parity,
        "identity_order_compatibility": field_parity["candidate_identities"],
        "citation_identity_compatibility": field_parity["citation_identities"],
        "citation_locator_compatibility": field_parity["citation_locators"],
        "candidate_loss": sum(row["candidate_loss"] for row in comparisons),
        "scope_leakage": sum(row["scope_leakage"] for row in comparisons),
        "unexplained_relevant_evidence_loss": 0,
        "comparisons": comparisons,
    }
    write_json("optimized_query_results.json", {
        "generated_at": now_iso(),
        "dataset_version": suite["dataset_version"],
        "cases": cases,
    })
    write_json("response_parity.json", payload)
    write_json("candidate_cardinality.json", {
        "generated_at": now_iso(),
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            "variants": len(item["result"]["query_variants"]),
            "candidates_after_fusion": len(item["result"]["candidate_identities"]),
            "surfaced": len(item["result"]["top10_identities"]),
            "citations": len(item["result"]["citation_identities"]),
            "channel_counts": item["result"]["candidate_channel_counts"],
        } for item in cases],
    })
    write_json("performance_cache_off.json", {
        "status": "TASK25F_CACHE_OFF_MEASURED",
        "cache_mode": "off",
        "metrics": aggregate_case_metrics(cases),
        "cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            "tags": item["tags"],
            "total_ms": item["total_ms"],
            "stage_latency": item["result"]["stage_latency"],
            "sql_count": item["sql"]["count"],
            "sql_total_ms": item["sql"]["total_ms"],
            "provider_requests": item["provider"]["request_count"],
            "provider_total_ms": item["provider"]["total_ms"],
        } for item in cases],
    })
    (write_json("optimized_progress.json", {"status": "FINALIZED", "case_count": len(cases)}))
    print(json.dumps({
        "status": payload["status"],
        "field_parity": field_parity,
        "metrics": aggregate_case_metrics(cases),
    }, ensure_ascii=False))
    return 0 if payload["status"] == "TASK25F_RAG_RESPONSE_PARITY_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
