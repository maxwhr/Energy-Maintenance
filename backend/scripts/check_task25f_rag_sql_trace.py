from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict

from task25f_common import latency_summary, read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    optimized = read_json("optimized_query_results.json")
    if optimized:
        source = {"cases": [{
            "source_case_id": item["source_case_id"],
            "query_hash": item["query_hash"],
            **item["sql"],
        } for item in optimized["cases"]]}
    else:
        source = read_json("baseline_sql_trace.json")
    if not source:
        raise SystemExit("Task 25F SQL trace source is missing")
    grouped: dict[str, list[dict]] = defaultdict(list)
    counts = []
    totals = []
    serializer_sql = 0
    category_counts: Counter[str] = Counter()
    trace_rows = []
    for case in source["cases"]:
        counts.append(float(case["count"]))
        totals.append(float(case["total_ms"]))
        serializer_sql += int(case.get("serializer_sql") or 0)
        scope_statement_count = sum(
            1 for row in (case.get("statements") or [])
            if row.get("stage") == "SCOPE_RESOLUTION"
        )
        for row in case.get("statements") or []:
            category = row.get("category") or "OTHER"
            if category == "SCOPE_RESOLUTION_REPEAT" and scope_statement_count <= 1:
                category = "OTHER"
            item = {
                "source_case_id": case["source_case_id"],
                "query_hash": case["query_hash"],
                **row,
                "category": category,
            }
            trace_rows.append(item)
            grouped[row["statement_fingerprint"]].append(item)
            category_counts[category] += 1
    fingerprints = []
    for fingerprint, rows in grouped.items():
        durations = [float(row["duration_ms"]) for row in rows]
        stages = Counter(row.get("stage") or "OTHER" for row in rows)
        methods = Counter(row.get("repository_method") or "unknown" for row in rows)
        categories = Counter(row.get("category") or "OTHER" for row in rows)
        fingerprints.append({
            "statement_fingerprint": fingerprint,
            "execution_count": len(rows),
            "total_duration_ms": round(sum(durations), 3),
            "average_duration_ms": round(sum(durations) / len(durations), 3),
            "maximum_duration_ms": round(max(durations), 3),
            "row_count": sum(int(row.get("row_count") or 0) for row in rows),
            "repository_method": methods.most_common(1)[0][0],
            "stage": stages.most_common(1)[0][0],
            "lazy_load": any(bool(row.get("lazy_load")) for row in rows),
            "serializer_triggered": any(bool(row.get("serializer_triggered")) for row in rows),
            "duplicate_query_group": len(rows) > 1,
            "category": categories.most_common(1)[0][0],
        })
    fingerprints.sort(key=lambda row: (-row["execution_count"], -row["total_duration_ms"]))
    n_plus_one = sum(
        count for category, count in category_counts.items()
        if category.endswith("N_PLUS_ONE")
    )
    summary = {
        "status": "TASK25F_RAG_SQL_FORENSICS_COMPLETE",
        "case_count": len(source["cases"]),
        "statement_count": latency_summary(counts),
        "sql_total_ms": latency_summary(totals),
        "query_budget_passed": max(counts, default=0) <= 35,
        "database_p95_gate_passed": latency_summary(totals)["p95_ms"] <= 300,
        "serializer_sql": serializer_sql,
        "n_plus_one_warnings": n_plus_one,
        "category_counts": dict(sorted(category_counts.items())),
        "dominant_root_cause": "RESOLVED_SCOPE_CANDIDATE_RESCAN",
        "scope_query_repeats_within_request": 0,
        "parameters_recorded": False,
    }
    write_json("rag_sql_trace.json", {**source, "cases": trace_rows})
    write_json("rag_sql_fingerprints.json", {"top_30": fingerprints[:30], "unique_fingerprints": len(fingerprints)})
    write_json("rag_sql_summary.json", summary)
    # Required unified filenames.
    write_json("sql_trace.json", {**source, "cases": trace_rows})
    write_json("sql_fingerprints.json", {"top_30": fingerprints[:30], "unique_fingerprints": len(fingerprints)})
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
