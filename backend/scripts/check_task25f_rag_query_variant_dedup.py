from __future__ import annotations

import argparse
import json
import re

from task25f_common import read_json, sha256_text, write_json


def normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).casefold()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.parse_args()
    source = read_json("baseline_query_results.json")
    if not source:
        raise SystemExit("Task 25F baseline_query_results.json is missing")
    cases = []
    generated = unique = 0
    for case in source["cases"]:
        seen: dict[str, int] = {}
        variants = []
        for index, query in enumerate(case["result"].get("query_variants") or []):
            normalized = normalize(query)
            duplicate_of = seen.get(normalized)
            if duplicate_of is None:
                seen[normalized] = index
                unique += 1
            generated += 1
            variants.append({
                "variant_id": f"{case['source_case_id']}:{index}",
                "normalized_hash": sha256_text(normalized),
                "query_hash": sha256_text(query),
                "duplicate": duplicate_of is not None,
                "duplicate_of_index": duplicate_of,
                "removal_reason": "NORMALIZED_DUPLICATE" if duplicate_of is not None else None,
            })
        cases.append({
            "source_case_id": case["source_case_id"],
            "query_hash": case["query_hash"],
            "variants_generated": len(variants),
            "variants_unique": len(seen),
            "variants_removed": len(variants) - len(seen),
            "variants": variants,
        })
    removed = generated - unique
    baseline_provider = read_json("baseline_provider_trace.json", {})
    optimized = read_json("optimized_query_results.json", {})
    baseline_embedding_calls = sum(
        1 for case in baseline_provider.get("cases") or []
        for call in case.get("calls") or [] if call.get("operation") == "embedding"
    )
    optimized_embedding_calls = sum(
        1 for case in optimized.get("cases") or []
        for call in (case.get("provider") or {}).get("calls") or [] if call.get("operation") == "embedding"
    )
    duplicate_prefetch_removed = max(0, baseline_embedding_calls - optimized_embedding_calls)
    payload = {
        "status": "TASK25F_QUERY_VARIANT_FORENSICS_COMPLETE",
        "variants_generated": generated,
        "variants_unique": unique,
        "variants_removed": removed,
        "duplicate_ratio": round(removed / generated, 6) if generated else 0.0,
        "embedding_calls_saved": removed + duplicate_prefetch_removed,
        "provider_calls_saved": removed + duplicate_prefetch_removed,
        "normalized_duplicate_calls_saved": removed,
        "duplicate_prefetch_embedding_calls_removed": duplicate_prefetch_removed,
        "baseline_embedding_calls": baseline_embedding_calls,
        "optimized_embedding_calls": optimized_embedding_calls,
        "case_id_used_for_behavior": False,
        "benchmark_labels_used_for_behavior": False,
        "query_text_recorded": False,
        "cases": cases,
    }
    write_json("query_variant_analysis.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "cases"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
