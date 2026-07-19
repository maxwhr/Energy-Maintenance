from __future__ import annotations

import csv
import json
from collections import Counter
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import MaintenanceSemanticAnchor
from task25b_r3_dev_r5_r5_common import OUT, SOURCE, now_iso, write_once


ITERATION = SOURCE / "canary_iteration_2.json"
SOURCE_DATASET = SOURCE / "train_dev_dataset_v1.json"
FIXED_DATASET = OUT / "train_dev_dataset_v1.json"
CSV_PATH = OUT / "ranking_forensics.csv"


SUPPORT_TERMS = {
    "CAUSE": ("cause", "reason", "原因", "导致"),
    "ACTION": ("check", "replace", "restart", "处理", "排查", "检查"),
    "PROCEDURE": ("step", "procedure", "步骤", "流程", "顺序"),
    "SAFETY": ("safety", "danger", "安全", "危险", "断电"),
    "PREREQUISITE": ("before", "prerequisite", "前提", "准备", "开始前"),
    "VERIFICATION": ("verify", "confirm", "验证", "确认", "恢复"),
    "ALARM_MEANING": ("alarm", "告警", "故障码", "含义"),
    "CONFIGURATION": ("configure", "parameter", "配置", "参数", "设置"),
    "GENERAL_INFORMATION": (),
}


def _candidate_ids(candidate: dict[str, Any]) -> set[str]:
    semantic = str(candidate.get("semantic_unit_id") or "")
    return {
        str(candidate.get("candidate_id") or ""), str(candidate.get("chunk_id") or ""), semantic,
        f"su:{semantic}" if semantic else "", *(str(value) for value in candidate.get("source_chunk_ids") or []),
    } - {""}


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
                output[unit_id] = list(dict.fromkeys([
                    *output.get(unit_id, []),
                    *(str(value) for value in fields.get("source_chunk_ids") or [str(anchor.source_chunk_id)]),
                ]))
    return output


def _expected(label: dict[str, Any], mapping: dict[str, list[str]]) -> set[str]:
    units = [str(value) for value in label.get("expected_semantic_unit_ids") or []]
    return {
        *(str(value) for value in label.get("expected_chunk_ids") or []),
        *units,
        *(f"su:{value}" for value in units),
        *(chunk for unit in units for chunk in mapping.get(unit, [])),
    }


def _matches(candidate: dict[str, Any], expected: set[str]) -> bool:
    return bool(_candidate_ids(candidate) & expected)


def _rank(ids: list[str], candidates: list[dict[str, Any]], expected: set[str]) -> int | None:
    by_id = {str(item.get("candidate_id")): item for item in candidates}
    for rank, candidate_id in enumerate(ids, start=1):
        item = by_id.get(str(candidate_id))
        if str(candidate_id) in expected or (item and _matches(item, expected)):
            return rank
    return None


def _ranking_ids(values: list[Any]) -> list[str]:
    return [str(value.get("candidate_id")) if isinstance(value, dict) else str(value) for value in values]


def _features(candidate: dict[str, Any] | None, requested: list[str]) -> dict[str, Any]:
    if candidate is None:
        return {}
    text = " ".join(str(candidate.get(key) or "") for key in ("document_title", "section_title", "quote")).lower()
    supported = [name for name in requested if not SUPPORT_TERMS.get(name) or any(term.lower() in text for term in SUPPORT_TERMS[name])]
    coverage = len(supported) / max(1, len(requested))
    locator = candidate.get("source_locator") or {}
    full_section = bool(candidate.get("semantic_unit_id") and "full" in text) or len(str(candidate.get("quote") or "")) > 1400
    generality = round(min(1.0, (0.55 if full_section else 0.0) + (0.25 if coverage == 0 else 0.0)), 4)
    specificity = round(max(0.0, 1.0 - generality), 4)
    direct = round(0.50 * coverage + 0.25 * specificity + 0.15 * bool(locator) + 0.10 * bool(candidate.get("semantic_unit_id")), 6)
    return {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_unit_type": "SEMANTIC_UNIT" if candidate.get("semantic_unit_id") else "CHUNK",
        "supported_requested_information": supported,
        "requested_information_coverage": round(coverage, 6),
        "intent_coverage": round(coverage, 6),
        "entity_match": bool(candidate.get("exact_model_match") or not candidate.get("exact_model_match")),
        "exact_model_match": bool(candidate.get("exact_model_match")),
        "exact_alarm_match": bool(candidate.get("exact_alarm_match")),
        "condition_match": None,
        "citation_quality": 1.0 if locator else 0.0,
        "source_specificity": specificity,
        "generality_score": generality,
        "direct_answer_score": direct,
        "rrf_breakdown": {
            "raw_ranks": candidate.get("raw_ranks") or {},
            "raw_scores": candidate.get("raw_scores") or {},
            "rrf_score": candidate.get("rrf_score"),
        },
        "rerank_breakdown": {
            "frozen_score": candidate.get("rerank_score"),
            "diagnostic_direct_answer_score": direct,
            "diagnostic_generality_penalty": generality,
        },
        "final_score": candidate.get("final_score"),
    }


def _reason(top: dict[str, Any] | None, expected_item: dict[str, Any] | None, requested: list[str], expected_models: list[str], expected_alarms: list[str]) -> str:
    if top is None:
        return "OTHER"
    top_features = _features(top, requested)
    expected_features = _features(expected_item, requested)
    if expected_models and not top.get("exact_model_match"):
        return "WRONG_MODEL"
    if expected_alarms and not top.get("exact_alarm_match"):
        return "WRONG_ALARM"
    if top_features.get("generality_score", 0) > expected_features.get("generality_score", 0):
        return "GENERIC_SECTION_OVER_SPECIFIC"
    if top_features.get("requested_information_coverage", 0) < expected_features.get("requested_information_coverage", 0):
        return "INSUFFICIENT_REQUESTED_INFO_COVERAGE"
    if top.get("rrf_score", 0) > (expected_item or {}).get("rrf_score", 0):
        return "RELEVANCE_GRADE_NOT_USED"
    top_votes = len((top or {}).get("raw_ranks") or {})
    expected_votes = len((expected_item or {}).get("raw_ranks") or {})
    if top_votes > expected_votes:
        return "MULTI_QUERY_VOTE_DOMINANCE"
    return "RELEVANCE_GRADE_NOT_USED"


def main() -> None:
    if CSV_PATH.exists():
        raise SystemExit("ranking forensics is already frozen")
    iteration = json.loads(ITERATION.read_text(encoding="utf-8"))
    labels = {row["case_id"]: row for row in json.loads(SOURCE_DATASET.read_text(encoding="utf-8"))["rows"]}
    fixed_by_query = {row["query"]: row for row in json.loads(FIXED_DATASET.read_text(encoding="utf-8"))["rows"]}
    mapping = _unit_mapping()
    rows = iteration["deterministic_only"]["rows"]
    output: list[dict[str, Any]] = []
    for row in rows:
        if row.get("no_answer") or row.get("requires_clarification") or not row.get("candidate_hit_at_50"):
            continue
        label = labels[row["case_id"]]
        fixed = fixed_by_query.get(label["query"], {})
        expected = _expected(label, mapping)
        candidates = row.get("raw_candidates") or []
        rrf_ids = _ranking_ids(row.get("rrf_ranking") or [])
        rerank_ids = _ranking_ids(row.get("rerank_ranking") or [])
        surfaced_values = row.get("surfaced_results") or []
        surfaced_ids = _ranking_ids(surfaced_values)
        rrf_rank = _rank(rrf_ids, candidates, expected)
        rerank_rank = _rank(rerank_ids, candidates, expected)
        surfaced_rank = _rank(surfaced_ids, candidates, expected)
        if surfaced_rank is not None and surfaced_rank <= 2:
            continue
        by_id = {str(item.get("candidate_id")): item for item in candidates}
        top = surfaced_values[0] if surfaced_values and isinstance(surfaced_values[0], dict) else (by_id.get(surfaced_ids[0]) if surfaced_ids else None)
        expected_item = next((item for item in candidates if _matches(item, expected)), None)
        requested = fixed.get("expected_requested_information") or []
        reason = _reason(top, expected_item, requested, row.get("expected_models") or [], row.get("expected_alarms") or [])
        output.append({
            "case_id": row["case_id"],
            "query": label["query"],
            "expected_relevance_grades": fixed.get("evaluation_identity", {}).get("relevance_grades") or {value: 3 for value in sorted(expected)},
            "candidate_rank_at_each_stage": {
                "channel_or_fused_top50": rrf_rank,
                "rrf": rrf_rank,
                "deterministic_rerank": rerank_rank,
                "refinement": surfaced_rank,
                "surfaced": surfaced_rank,
            },
            "requested_information": requested,
            "wrong_top_candidate": _features(top, requested),
            "expected_candidate": _features(expected_item, requested),
            "wrong_top_candidate_reason": reason,
            "relevant_evidence_lost_by_refinement": bool(rerank_rank is not None and surfaced_rank is None),
        })
    counts = Counter(item["wrong_top_candidate_reason"] for item in output)
    summary = {
        "generated_at": now_iso(),
        "baseline": "task25b_r3_dev_r5_r4_mm iteration 2 deterministic-only",
        "ranking_error_cases": len(output),
        "primary_reason_counts": dict(sorted(counts.items())),
        "top50_but_not_top5": sum((item["candidate_rank_at_each_stage"]["surfaced"] or 999) > 5 for item in output),
        "top5_but_not_top2": sum(2 < (item["candidate_rank_at_each_stage"]["surfaced"] or 999) <= 5 for item in output),
        "forensics_completed_before_rerank_v2": True,
    }
    write_once("ranking_forensics.json", {**summary, "rows": output})
    write_once("ranking_error_summary.json", summary)
    fields = ["case_id", "wrong_top_candidate_reason", "requested_information", "candidate_rank_at_each_stage", "relevant_evidence_lost_by_refinement"]
    with CSV_PATH.open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in output:
            writer.writerow({key: json.dumps(item.get(key), ensure_ascii=False) if isinstance(item.get(key), (list, dict)) else item.get(key) for key in fields})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
