from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import MaintenanceSemanticAnchor
from task25b_r3_dev_r5_r5_common import OUT, SOURCE, now_iso, write_once


ITERATION = SOURCE / "canary_iteration_2.json"
SOURCE_DATASET = SOURCE / "train_dev_dataset_v1.json"
FIXED_DATASET = OUT / "train_dev_dataset_v1.json"
CSV_PATH = OUT / "candidate_miss_forensics.csv"


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _unit_mapping() -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    with SessionLocal() as db:
        anchors = db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.namespace == "pilot_r5_query_aware",
            MaintenanceSemanticAnchor.current_version.is_(True),
        )).all()
        for anchor in anchors:
            fields = dict(anchor.semantic_fields or {})
            unit_id = str(fields.get("semantic_unit_id") or "")
            if unit_id:
                output[unit_id] = _unique([
                    *output.get(unit_id, []),
                    *(fields.get("source_chunk_ids") or [str(anchor.source_chunk_id)]),
                ])
    return output


def _candidate_ids(candidate: dict[str, Any]) -> set[str]:
    semantic = str(candidate.get("semantic_unit_id") or "")
    return {
        str(candidate.get("candidate_id") or ""),
        str(candidate.get("chunk_id") or ""),
        semantic,
        f"su:{semantic}" if semantic else "",
        *(str(value) for value in candidate.get("source_chunk_ids") or []),
    } - {""}


def _expected_ids(label: dict[str, Any], mapping: dict[str, list[str]]) -> set[str]:
    units = _unique(label.get("expected_semantic_unit_ids") or [])
    chunks = _unique(label.get("expected_chunk_ids") or [])
    return {
        *units,
        *(f"su:{value}" for value in units),
        *chunks,
        *(chunk for unit in units for chunk in mapping.get(unit, [])),
    }


def _matches(candidate: dict[str, Any], expected: set[str]) -> bool:
    return bool(_candidate_ids(candidate) & expected)


def _channel_trace(candidates: list[dict[str, Any]], expected: set[str]) -> tuple[dict[str, list[dict]], dict[str, int | None]]:
    grouped: dict[str, list[dict]] = {}
    ranks: dict[str, int | None] = {}
    for candidate in candidates:
        for key, raw_rank in (candidate.get("raw_ranks") or {}).items():
            channel = key.split(":", 1)[0]
            grouped.setdefault(channel, []).append({
                "candidate_id": candidate.get("candidate_id"),
                "semantic_unit_id": candidate.get("semantic_unit_id"),
                "source_chunk_ids": candidate.get("source_chunk_ids") or [],
                "raw_rank": int(raw_rank),
                "query_trace": key,
                "expected_identity_match": _matches(candidate, expected),
            })
            if _matches(candidate, expected):
                previous = ranks.get(channel)
                ranks[channel] = int(raw_rank) if previous is None else min(previous, int(raw_rank))
    for channel, values in grouped.items():
        values.sort(key=lambda value: (value["raw_rank"], str(value["candidate_id"])))
        grouped[channel] = values
        ranks.setdefault(channel, None)
    return grouped, ranks


def _rank(candidate_ids: list[str], candidates: list[dict[str, Any]], expected: set[str]) -> int | None:
    by_id = {str(item.get("candidate_id")): item for item in candidates}
    for rank, candidate_id in enumerate(candidate_ids, start=1):
        candidate = by_id.get(str(candidate_id))
        if candidate and _matches(candidate, expected):
            return rank
        if str(candidate_id) in expected:
            return rank
    return None


def _ranking_ids(values: list[Any]) -> list[str]:
    return [str(value.get("candidate_id")) if isinstance(value, dict) else str(value) for value in values]


def _reason(row: dict[str, Any], label: dict[str, Any], mapping: dict[str, list[str]]) -> tuple[str, list[str]]:
    candidates = row.get("raw_candidates") or []
    if row.get("requires_clarification"):
        return "EVALUATION_IDENTITY_MISMATCH", [
            "retrieval intentionally stopped at clarification boundary",
            "candidate recall is not applicable until clarification is resolved",
        ]
    if not candidates or not row.get("generated_queries"):
        return "PLANNER_QUERY_MISSING", ["no query variant or candidate trace was executed"]
    channels = set(row.get("actual_channels") or [])
    units = label.get("expected_semantic_unit_ids") or []
    expected_source = {chunk for unit in units for chunk in mapping.get(str(unit), [])}
    observed_source = {chunk for candidate in candidates for chunk in candidate.get("source_chunk_ids") or []}
    if expected_source & observed_source:
        return "SEMANTIC_UNIT_IDENTITY_MISMATCH", [
            "a mapped source chunk was retained but the expected unit identity was not credited"
        ]
    if units and "SEMANTIC_UNIT" not in channels:
        return "ANCHOR_TYPE_TOO_NARROW", [
            "fast path executed keyword-only channels",
            "the frozen label targets a specific Semantic Unit",
        ]
    if "SEMANTIC_UNIT" in channels:
        return "SEMANTIC_UNIT_NO_RECALL", ["semantic channel executed but expected mapped identity was absent"]
    return "CHANNEL_BUDGET_TOO_SMALL", ["expected evidence was absent from the retained per-channel budget"]


def main() -> None:
    if CSV_PATH.exists():
        raise SystemExit("candidate miss forensics is already frozen")
    iteration = json.loads(ITERATION.read_text(encoding="utf-8"))
    source_rows = json.loads(SOURCE_DATASET.read_text(encoding="utf-8"))["rows"]
    labels = {row["case_id"]: row for row in source_rows}
    fixed_rows = json.loads(FIXED_DATASET.read_text(encoding="utf-8"))["rows"]
    fixed_by_query = {row["query"]: row for row in fixed_rows}
    mapping = _unit_mapping()
    baseline_rows = iteration["deterministic_only"]["rows"]
    misses = [row for row in baseline_rows if not row.get("no_answer") and not row.get("candidate_hit_at_50")]
    output: list[dict[str, Any]] = []
    for row in misses:
        label = labels[row["case_id"]]
        fixed = fixed_by_query.get(label["query"], {})
        expected = _expected_ids(label, mapping)
        candidates = row.get("raw_candidates") or []
        channel_top, channel_expected_ranks = _channel_trace(candidates, expected)
        primary, secondary = _reason(row, label, mapping)
        units = _unique(label.get("expected_semantic_unit_ids") or [])
        rrf_ids = _ranking_ids(row.get("rrf_ranking") or [])
        rerank_ids = _ranking_ids(row.get("rerank_ranking") or [])
        surfaced_ids = _ranking_ids(row.get("surfaced_results") or [])
        output.append({
            "case_id": row["case_id"],
            "original_query": label["query"],
            "canonical_query": row.get("canonical_query"),
            "primary_intent": row.get("actual_intent"),
            "requested_information": fixed.get("expected_requested_information") or [],
            "confirmed_facts": {
                "device_models": row.get("actual_models") or [],
                "alarm_codes": row.get("actual_alarms") or [],
            },
            "normalized_conditions": [],
            "query_variants": row.get("generated_queries") or [],
            "requested_channels": row.get("requested_channels") or [],
            "executed_channels": row.get("actual_channels") or [],
            "channel_raw_top_k": channel_top,
            "channel_expected_evidence_rank": channel_expected_ranks,
            "channel_internal_aggregate_rank": _rank(rrf_ids, candidates, expected),
            "rrf_rank": _rank(rrf_ids, candidates, expected),
            "deterministic_rerank_rank": _rank(rerank_ids, candidates, expected),
            "refinement_rank": _rank(surfaced_ids, candidates, expected),
            "surfaced_rank": _rank(surfaced_ids, candidates, expected),
            "semantic_unit_source_chunk_mapping": {
                unit: mapping.get(unit, []) for unit in units
            },
            "evaluation_identity_mapping": {
                "expected_semantic_unit_ids": units,
                "expected_chunk_ids": label.get("expected_chunk_ids") or [],
                "expected_document_ids": label.get("expected_document_ids") or [],
                "equivalent_evidence_ids": sorted(expected),
            },
            "filtered_reason": (
                "clarification_boundary" if row.get("requires_clarification")
                else "not_observed_in_frozen_top50"
            ),
            "primary_reason": primary,
            "secondary_reasons": secondary,
            "trace_limit": "frozen iteration-2 retained candidates; no benchmark label was passed to retrieval",
        })
    counts = Counter(item["primary_reason"] for item in output)
    summary = {
        "generated_at": now_iso(),
        "baseline": "task25b_r3_dev_r5_r4_mm iteration 2 deterministic-only",
        "total_misses": len(output),
        "primary_reason_counts": dict(sorted(counts.items())),
        "unknown": counts.get("UNKNOWN", 0),
        "unique_primary_reason_per_case": all(bool(item["primary_reason"]) for item in output),
        "forensics_completed_before_ranking_weight_changes": True,
    }
    write_once("candidate_miss_forensics.json", {**summary, "rows": output})
    write_once("candidate_miss_summary.json", summary)
    fields = ["case_id", "primary_intent", "primary_reason", "requested_channels", "executed_channels", "rrf_rank", "surfaced_rank", "secondary_reasons"]
    with CSV_PATH.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in output:
            writer.writerow({key: json.dumps(item.get(key), ensure_ascii=False) if isinstance(item.get(key), (list, dict)) else item.get(key) for key in fields})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
