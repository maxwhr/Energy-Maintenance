from __future__ import annotations

import json
from collections import defaultdict
from unittest.mock import patch

from task25f_r1_common import RUNTIME, read_json, sha256_value, write_csv, write_json

from app.core.database import SessionLocal
from app.services.embedding_service import EmbeddingService
from app.services.rag_compatibility_diff_service import RagCompatibilityDiffService
from app.services.rag_compatibility_replay_service import RagCompatibilityReplayService
from app.services.rag_raw_channel_snapshot import snapshot_from_dict
from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


FIELDS = (
    "query_understanding_hash",
    "query_variant_hashes",
    "requested_channels",
    "actual_channels",
    "raw_candidate_identities",
    "candidate_identities",
    "rrf_order",
    "rerank_order",
    "refinement_survivors",
    "top5_identities",
    "top10_identities",
    "citation_identities",
    "citation_locators",
    "confidence_status",
    "no_answer",
    "needs_clarification",
    "scope_leakage",
)


def main() -> int:
    manifest = read_json("channel_snapshot_manifest.json", {})
    integrity = read_json("snapshot_integrity.json", {})
    if not integrity.get("passed"):
        raise SystemExit("snapshot integrity must pass before replay")
    contexts = {item["case_id"]: item for item in manifest.get("contexts") or []}
    by_case = defaultdict(list)
    for line in (RUNTIME / "channel_snapshots.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            snapshot = snapshot_from_dict(json.loads(line))
            by_case[snapshot.case_id].append(snapshot)
    provider_attempts = {"embedding": 0, "dashvector": 0}

    def blocked_embedding(*_args, **_kwargs):
        provider_attempts["embedding"] += 1
        raise AssertionError("embedding access is forbidden during deterministic replay")

    def blocked_dashvector(*_args, **_kwargs):
        provider_attempts["dashvector"] += 1
        raise AssertionError("DashVector access is forbidden during deterministic replay")

    comparisons = []
    diffs = []
    with SessionLocal() as db, patch.object(EmbeddingService, "embed_texts", blocked_embedding), patch.object(
        DashVectorAdapter, "query_vectors", blocked_dashvector
    ):
        service = RagCompatibilityReplayService(db)
        differ = RagCompatibilityDiffService()
        for context in manifest.get("contexts") or []:
            case_id = context["case_id"]
            reference = service.replay(
                context=context,
                snapshots=by_case.get(case_id, []),
                mode="SEQUENTIAL_REFERENCE",
            )
            optimized = service.replay(
                context=context,
                snapshots=list(reversed(by_case.get(case_id, []))),
                mode="OPTIMIZED_REPLAY",
            )
            field_checks = {field: reference.output.get(field) == optimized.output.get(field) for field in FIELDS}
            diff = differ.compare(reference, optimized)
            comparisons.append({
                "case_id": case_id,
                "passed": all(field_checks.values()) and not diff["first_divergent_stage"],
                "fields": field_checks,
                "reference_hash": sha256_value(reference.output),
                "optimized_hash": sha256_value(optimized.output),
                "first_divergent_stage": diff["first_divergent_stage"],
                "reason": diff["reason"],
                "reference_diagnostics": reference.diagnostics,
                "optimized_diagnostics": optimized.diagnostics,
            })
            diffs.append(diff)
    parity = {
        field: round(sum(item["fields"][field] for item in comparisons) / len(comparisons), 6)
        for field in FIELDS
    }
    hard_fields = (
        "candidate_identities", "rrf_order", "top5_identities", "top10_identities",
        "citation_identities", "citation_locators", "confidence_status", "no_answer",
        "needs_clarification", "scope_leakage",
    )
    passed = (
        len(comparisons) == 60
        and all(parity[field] == 1.0 for field in hard_fields)
        and all(item["passed"] for item in comparisons)
        and not any(provider_attempts.values())
    )
    payload = {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "case_count": len(comparisons),
        "modes": ["SEQUENTIAL_REFERENCE", "OPTIMIZED_REPLAY"],
        "same_raw_snapshot": True,
        "snapshot_manifest_hash": manifest.get("manifest_hash"),
        "provider_calls_during_replay": sum(provider_attempts.values()),
        "provider_attempts": provider_attempts,
        "field_parity": parity,
        "first_divergent_stage_counts": {
            stage: sum(item["first_divergent_stage"] == stage for item in diffs)
            for stage in sorted({item["first_divergent_stage"] for item in diffs if item["first_divergent_stage"]})
        },
        "unknown_reason_count": sum(item["reason"] == "UNKNOWN" for item in diffs),
        "comparisons": comparisons,
    }
    write_json("replay_parity.json", payload)
    write_csv(
        "replay_case_diffs.csv",
        [{
            "case_id": item["case_id"],
            "first_divergent_stage": item["first_divergent_stage"],
            "reference_hash": item["reference_hash"],
            "optimized_hash": item["optimized_hash"],
            "missing_ids": json.dumps(item["missing_ids"], ensure_ascii=False),
            "added_ids": json.dumps(item["added_ids"], ensure_ascii=False),
            "rank_changes": json.dumps(item["rank_changes"], ensure_ascii=False),
            "citation_changes": json.dumps(item["citation_changes"], ensure_ascii=False),
            "channel_status_changes": item["channel_status_changes"],
            "reason": item["reason"],
            "severity": item["severity"],
            "fix_required": item["fix_required"],
        } for item in diffs],
        [
            "case_id", "first_divergent_stage", "reference_hash", "optimized_hash",
            "missing_ids", "added_ids", "rank_changes", "citation_changes",
            "channel_status_changes", "reason", "severity", "fix_required",
        ],
    )
    print(json.dumps({
        "status": payload["status"],
        "cases": payload["case_count"],
        "candidate_parity": parity["candidate_identities"],
        "top5_parity": parity["top5_identities"],
        "citation_parity": parity["citation_identities"],
        "provider_calls": payload["provider_calls_during_replay"],
        "divergent_cases": sum(not item["passed"] for item in comparisons),
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
