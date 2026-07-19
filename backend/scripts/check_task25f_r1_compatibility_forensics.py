from __future__ import annotations

import json
from collections import Counter

from task25f_r1_common import TASK25F_RUNTIME, read_json, write_json


def _source(name: str) -> dict:
    return json.loads((TASK25F_RUNTIME / name).read_text(encoding="utf-8"))


def main() -> int:
    replay = read_json("replay_parity.json", {})
    original = _source("response_parity.json")
    provider = _source("provider_trace.json")
    failed_provider_cases = {
        item.get("source_case_id")
        for item in provider.get("calls") or []
        if item.get("operation") == "semantic_unit" and not item.get("success")
    }
    cases = []
    for item in original.get("comparisons") or []:
        fields = item.get("fields") or {}
        if item.get("passed"):
            first_stage = None
            reason = "NO_DIFFERENCE"
            severity = "NONE"
            fix_required = False
        elif item.get("source_case_id") in failed_provider_cases:
            first_stage = "CHANNEL_RAW_RESULT"
            reason = "PROVIDER_PARTIAL_FAILURE"
            severity = "P0_EXTERNAL"
            fix_required = True
        else:
            # Task 25F retained only final projected identities. Without an
            # immutable raw response, the historical first local divergence
            # cannot be reconstructed; R1 fixes that evidence gap.
            first_stage = "CHANNEL_RAW_RESULT"
            reason = "BASELINE_ARTIFACT_INCOMPLETE"
            severity = "FORENSIC_GAP"
            fix_required = False
        cases.append({
            "case_id": item.get("source_case_id"),
            "first_divergent_stage": first_stage,
            "reference_hash": None,
            "optimized_hash": None,
            "missing_ids": [],
            "added_ids": [],
            "rank_changes": [],
            "citation_changes": not fields.get("citation_identities", True) or not fields.get("citation_locators", True),
            "channel_status_changes": not fields.get("actual_channels", True),
            "reason": reason,
            "severity": severity,
            "fix_required": fix_required,
            "fields_before_first_divergence_consistent": all(
                fields.get(name, True) for name in ("query_understanding", "query_variants", "requested_channels")
            ),
        })
    reasons = Counter(item["reason"] for item in cases)
    deterministic_pass = bool(replay.get("passed")) and not replay.get("first_divergent_stage_counts")
    payload = {
        "status": "PASSED" if deterministic_pass else "FAILED",
        "deterministic_replay_compatible": deterministic_pass,
        "deterministic_first_divergent_stage": None if deterministic_pass else replay.get("first_divergent_stage_counts"),
        "deterministic_unknown_count": replay.get("unknown_reason_count"),
        "historical_task25f_status": "TASK25F_RAG_COMPATIBILITY_FAILED",
        "historical_case_count": len(cases),
        "historical_difference_count": sum(item["reason"] != "NO_DIFFERENCE" for item in cases),
        "historical_reason_counts": dict(sorted(reasons.items())),
        "semantic_partial_failure_cases": sorted(failed_provider_cases),
        "historical_raw_snapshot_available": False,
        "r1_raw_snapshot_available": True,
        "code_regression_found_by_replay": not deterministic_pass,
        "live_provider_variance_pending_aa_confirmation": True,
        "cases": cases,
    }
    write_json("compatibility_forensics.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "deterministic_replay": deterministic_pass,
        "historical_differences": payload["historical_difference_count"],
        "partial_failure_cases": len(failed_provider_cases),
        "unknown": payload["deterministic_unknown_count"],
    }, ensure_ascii=False))
    return 0 if deterministic_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
