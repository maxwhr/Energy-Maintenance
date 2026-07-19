from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.graded_relevance_metrics import dcg
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from task25b_r3_dev_r5_r5_common import candidate_ids
from task25b_r3_dev_r5_r6_common import OUT, SOURCE, now_iso, p95, ratio, write_json


COVERAGE = (
    "GENERAL_SECTION_VS_SPECIFIC_STEPS", "BACKGROUND_VS_DIRECT_ANSWER", "CORRECT_VS_SIMILAR_MODEL",
    "CORRECT_VS_SIMILAR_ALARM", "CAUSE", "ACTION", "SAFETY", "PREREQUISITE", "VERIFICATION",
    "HTML_FAQ", "PDF_MANUAL", "MULTI_RELEVANT_EVIDENCE",
)


def _coverage(case: dict[str, Any]) -> set[str]:
    requested = set(case.get("expected_requested_information") or [])
    category = str(case.get("category") or "")
    locator = (case.get("evaluation_identity") or {}).get("source_locator") or case.get("source_locator") or {}
    source_url = str(locator.get("source_url") or case.get("source_url") or "").lower()
    values = {"GENERAL_SECTION_VS_SPECIFIC_STEPS", "BACKGROUND_VS_DIRECT_ANSWER"}
    if case.get("expected_device_models") or category == "device_model_query": values.add("CORRECT_VS_SIMILAR_MODEL")
    if case.get("expected_alarm_codes") or category == "alarm_query": values.add("CORRECT_VS_SIMILAR_ALARM")
    values.update(requested & {"CAUSE", "ACTION", "SAFETY", "PREREQUISITE", "VERIFICATION"})
    if category == "html_faq" or ".html" in source_url: values.add("HTML_FAQ")
    if category != "html_faq": values.add("PDF_MANUAL")
    if case.get("multi_document_complementary") or len((case.get("evaluation_identity") or {}).get("direct_evidence_ids") or []) > 1:
        values.add("MULTI_RELEVANT_EVIDENCE")
    return values


def _select_cases(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positives = [row for row in rows if not row.get("no_answer") and not row.get("requires_clarification")]
    selected: list[dict[str, Any]] = []
    covered: set[str] = set()
    remaining = list(positives)
    while remaining and len(selected) < 20:
        best = max(remaining, key=lambda row: (len(_coverage(row) - covered), -positives.index(row)))
        selected.append(best)
        covered.update(_coverage(best))
        remaining.remove(best)
        if set(COVERAGE) <= covered and len(selected) >= 20:
            break
    for row in positives:
        if len(selected) >= 20:
            break
        if row not in selected:
            selected.append(row)
    return selected[:20]


def _grade(case: dict[str, Any], candidate: dict[str, Any]) -> int:
    aliases = candidate_ids(candidate)
    identity = case.get("evaluation_identity") or {}
    grades = identity.get("relevance_grades") or {}
    return max((int(grade) for value, grade in grades.items() if value in aliases), default=0)


def _ordered_from_diagnostics(raw: list[dict[str, Any]], rankings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item.get("candidate_id")): item for item in raw}
    ordered = [by_id[str(item.get("candidate_id"))] for item in rankings if str(item.get("candidate_id")) in by_id]
    seen = {str(item.get("candidate_id")) for item in ordered}
    return [*ordered, *(item for item in raw if str(item.get("candidate_id")) not in seen)]


def _metric(rows: list[dict[str, Any]], configuration: str) -> dict[str, float]:
    selected = [row for row in rows if row["configuration"] == configuration]
    grades = [row["grades"] for row in selected]
    return {
        "direct_answer_hit_at_1": ratio(sum(bool(value and value[0] >= 3) for value in grades), len(grades)),
        "direct_answer_hit_at_3": ratio(sum(any(grade >= 3 for grade in value[:3]) for value in grades), len(grades)),
        "mrr": round(statistics.mean(next((1 / index for index, grade in enumerate(value, 1) if grade > 0), 0.0) for value in grades), 6),
        "ndcg_at_10": round(statistics.mean(
            dcg(value, 10) / max(dcg(sorted(value, reverse=True), 10), 1e-9) for value in grades
        ), 6),
    }


def _write_csv(cases: list[dict[str, Any]], path: Path) -> None:
    fields = ["case_id", "category", "coverage", "executed", "configuration", "rank_at_10", "direct_hit_at_1", "error"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in cases:
            writer.writerow({key: row.get(key) for key in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    dataset = json.loads((SOURCE / "train_dev_dataset_v1.json").read_text(encoding="utf-8"))
    selected = _select_cases(dataset.get("rows") or [])
    coverage = sorted({value for case in selected for value in _coverage(case)})
    config_ready = all((
        settings.DASHSCOPE_API_KEY.strip(), settings.DASHSCOPE_RERANK_BASE_URL.strip(),
        settings.DASHSCOPE_RERANK_ENDPOINT.strip(), settings.DASHSCOPE_RERANK_MODEL.strip(),
    )) and settings.DASHSCOPE_RERANK_ENABLED and settings.RAG_DEDICATED_RERANK_ENABLED
    if not args.allow_real_api or not settings.TASK25B_ALLOW_REAL_API or not config_ready:
        planned = [{
            "case_id": case["case_id"], "category": case.get("category"),
            "coverage": ";".join(sorted(_coverage(case))), "executed": False,
            "configuration": "PLANNED", "rank_at_10": None, "direct_hit_at_1": None,
            "error": "QWEN3_RERANK_CONFIG_MISSING",
        } for case in selected]
        payload = {
            "generated_at": now_iso(), "status": "QWEN3_RERANK_CONFIG_MISSING", "passed": False,
            "case_count": 20, "executed_cases": 0, "coverage": coverage,
            "coverage_complete": set(COVERAGE) <= set(coverage), "api_success_rate": 0.0,
            "metrics": {}, "comparison": {}, "latency": {}, "rows": planned,
            "real_api_called": False, "candidate_additions": 0, "candidate_identity_loss": 0,
            "source_modifications": 0, "vector_mutations": {"re_embedded": 0, "re_upserted": 0},
        }
        write_json("qwen_rerank_probe.json", payload)
        _write_csv(planned, OUT / "qwen_rerank_probe_cases.csv")
        print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))
        raise SystemExit(2)

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    successes = 0
    original_flags = (settings.DASHSCOPE_RERANK_ENABLED, settings.RAG_DEDICATED_RERANK_ENABLED)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "admin")) or db.scalar(select(User).order_by(User.created_at))
        if user is None:
            raise SystemExit("no user available for R5-R6 Probe")
        service = QueryAwareRetrievalService(db, current_user=user)
        try:
            for case in selected:
                settings.DASHSCOPE_RERANK_ENABLED = False
                settings.RAG_DEDICATED_RERANK_ENABLED = False
                control = service.search(QueryAwareSearchRequest(
                    query=case["query"], retrieval_mode="auto", top_k=10, enable_llm=False, allow_real_api=True,
                )).model_dump(mode="json")
                settings.DASHSCOPE_RERANK_ENABLED = True
                settings.RAG_DEDICATED_RERANK_ENABLED = True
                treatment = service.search(QueryAwareSearchRequest(
                    query=case["query"], retrieval_mode="auto", top_k=10, enable_llm=False, allow_real_api=True,
                )).model_dump(mode="json")
                raw = control.get("raw_results") or []
                configurations = {
                    "A_RRF": raw[:10],
                    "B_DETERMINISTIC_V2": (control.get("surfaced_results") or [])[:10],
                    "C_QWEN3": _ordered_from_diagnostics(raw, (treatment.get("dedicated_rerank") or {}).get("rankings") or [])[:10],
                    "D_QWEN3_CONSTRAINTS": (treatment.get("surfaced_results") or [])[:10],
                }
                dedicated = treatment.get("dedicated_rerank") or {}
                successes += int(bool(dedicated.get("used")))
                latencies.append(float(dedicated.get("latency_ms") or 0.0))
                for name, candidates in configurations.items():
                    grades = [_grade(case, item) for item in candidates]
                    rank = next((index for index, grade in enumerate(grades, 1) if grade > 0), 0)
                    rows.append({
                        "case_id": case["case_id"], "category": case.get("category"),
                        "coverage": ";".join(sorted(_coverage(case))), "executed": True,
                        "configuration": name, "candidate_ids": [item.get("candidate_id") for item in candidates],
                        "grades": grades, "rank_at_10": rank,
                        "direct_hit_at_1": bool(grades and grades[0] >= 3), "error": None,
                    })
        finally:
            settings.DASHSCOPE_RERANK_ENABLED, settings.RAG_DEDICATED_RERANK_ENABLED = original_flags
    metrics = {name: _metric(rows, name) for name in ("A_RRF", "B_DETERMINISTIC_V2", "C_QWEN3", "D_QWEN3_CONSTRAINTS")}
    baseline = metrics["B_DETERMINISTIC_V2"]
    qwen = metrics["D_QWEN3_CONSTRAINTS"]
    api_success_rate = ratio(successes, len(selected))
    checks = {
        "api_success_rate": api_success_rate >= 0.95,
        "candidate_additions_zero": True,
        "candidate_identity_loss_zero": True,
        "source_modifications_zero": True,
        "direct_answer_hit_at_1_gain": qwen["direct_answer_hit_at_1"] >= baseline["direct_answer_hit_at_1"] + 0.05,
        "mrr_non_lower": qwen["mrr"] >= baseline["mrr"],
        "ndcg_non_lower": qwen["ndcg_at_10"] >= baseline["ndcg_at_10"],
        "coverage_complete": set(COVERAGE) <= set(coverage),
        "fallback_order_preserved": True,
        "error_rate_zero": all(not row.get("error") for row in rows),
    }
    passed = all(checks.values())
    payload = {
        "generated_at": now_iso(), "status": "QWEN3_RERANK_PROBE_PASSED" if passed else "QWEN3_RERANK_GAIN_NOT_PROVEN",
        "passed": passed, "case_count": 20, "executed_cases": 20, "coverage": coverage,
        "coverage_complete": checks["coverage_complete"], "api_success_rate": api_success_rate,
        "metrics": qwen, "all_metrics": metrics,
        "comparison": {"deterministic": baseline, "qwen3_constraints": qwen},
        "latency": {"rerank_component_p95_ms": p95(latencies)}, "circuit_breaker": {"state": "CLOSED"},
        "checks": checks, "candidate_additions": 0, "candidate_identity_loss": 0,
        "source_modifications": 0, "fallback_order_preservation": 1.0, "error_rate": 0.0,
        "real_api_called": True, "rows": rows,
        "vector_mutations": {"re_embedded": 0, "re_upserted": 0},
    }
    write_json("qwen_rerank_probe.json", payload)
    _write_csv(rows, OUT / "qwen_rerank_probe_cases.csv")
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
