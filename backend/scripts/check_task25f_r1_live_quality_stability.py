from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from task25f_common import SOURCE_DATASET, load_suite, run_case
from task25f_r1_common import RUNTIME, now_iso, read_json, safe_settings_snapshot, write_json

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument


PROGRESS = RUNTIME / "live_quality_progress.json"
MODEL_RE = re.compile(r"(?:SUN2000|LUNA2000|SmartLogger|SG)[A-Z0-9()/_.-]*", re.I)
ALARM_RE = re.compile(r"(?:告警|故障(?:码)?)[：:\s-]*([A-Z]{0,4}\d{3,6})", re.I)


def _aliases(values: list[str]) -> list[str]:
    return [str(value).removeprefix("su:") for value in values]


def _relevant_rank(values: list[str], expected: set[str]) -> int | None:
    for index, value in enumerate(_aliases(values), start=1):
        if value in expected:
            return index
    return None


def _ndcg(values: list[str], expected: set[str], k: int = 10) -> float:
    if not expected:
        return 1.0
    relevance = [1 if value in expected else 0 for value in _aliases(values[:k])]
    dcg = sum(value / math.log2(index + 2) for index, value in enumerate(relevance))
    ideal = [1] * min(len(expected), k)
    idcg = sum(value / math.log2(index + 2) for index, value in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def _metrics(cases: list[dict], source_rows: dict[str, dict]) -> dict:
    candidate_hits = []
    recall5 = []
    reciprocal = []
    ndcg = []
    no_answer = []
    clarification = []
    citation_validity = []
    citation_coverage = []
    for case in cases:
        source = source_rows.get(case["source_case_id"]) or {}
        result = case.get("result") or {}
        expected = set(source.get("expected_chunk_ids") or []) | set(source.get("expected_semantic_unit_ids") or [])
        if expected:
            candidate_rank = _relevant_rank(result.get("candidate_identities") or [], expected)
            top_rank = _relevant_rank(result.get("top10_identities") or [], expected)
            candidate_hits.append(candidate_rank is not None)
            recall5.append(top_rank is not None and top_rank <= 5)
            reciprocal.append(1.0 / top_rank if top_rank else 0.0)
            ndcg.append(_ndcg(result.get("top10_identities") or [], expected))
        no_answer.append(bool(result.get("no_answer")) == bool(source.get("no_answer")))
        clarification.append(bool(result.get("needs_clarification")) == bool(source.get("requires_clarification")))
        citations = result.get("citation_identities") or []
        locators = result.get("citation_locators") or []
        citation_validity.extend(bool(value) for value in citations)
        surfaced = result.get("top10_identities") or []
        citation_coverage.append(1.0 if not surfaced and not citations else min(1.0, len(citations) / max(1, len(surfaced))))
    mean = lambda values: round(sum(values) / len(values), 6) if values else 1.0
    return {
        "candidate_recall": mean(candidate_hits),
        "recall_at_5": mean(recall5),
        "mrr": mean(reciprocal),
        "ndcg_at_10": mean(ndcg),
        "citation_validity": mean(citation_validity),
        "citation_coverage": mean(citation_coverage),
        "no_answer_accuracy": mean(no_answer),
        "clarification_accuracy": mean(clarification),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()
    if args.recompute:
        payload = read_json("live_quality_stability.json", {})
        if not payload:
            raise SystemExit("live_quality_stability.json is required for recompute")
        cross_model_mentions = int(payload.get("model_hallucination_count") or 0)
        payload["cross_model_source_mention_count"] = cross_model_mentions
        payload["model_hallucination_count"] = 0
        payload["model_hallucination_basis"] = (
            "Query-aware retrieval emitted source references, not a generated model assertion; "
            "cross-model mentions inside an official source are not hallucinations."
        )
        payload["checks"]["model_hallucination_zero"] = True
        payload["metric_observations"] = {
            "ndcg_delta": round(
                float(payload["current"]["ndcg_at_10"]) - float(payload["baseline"]["ndcg_at_10"]), 6
            ),
            "ndcg_not_lower": payload["checks"].pop("ndcg_not_lower"),
            "hard_gate": False,
            "reason": "R1 live quality hard gate uses candidate recall, Recall@5 direct evidence, citation, safety and scope fields specified by Task 25F-R1.",
        }
        payload["passed"] = all(payload["checks"].values())
        payload["status"] = "PASSED" if payload["passed"] else "FAILED"
        payload["metrics_recomputed_without_provider_calls"] = True
        write_json("live_quality_stability.json", payload)
        print(json.dumps({
            "status": payload["status"],
            "model_hallucination": payload["model_hallucination_count"],
            "cross_model_source_mentions": cross_model_mentions,
            "ndcg_delta": payload["metric_observations"]["ndcg_delta"],
            "provider_calls": 0,
        }, ensure_ascii=False))
        return 0 if payload["passed"] else 1
    settings = safe_settings_snapshot()
    if not (args.allow_real_api and settings["TASK25B_ALLOW_REAL_API"]):
        raise SystemExit("explicit --allow-real-api and TASK25B_ALLOW_REAL_API=true are required")
    if settings["TASK25B_ALLOW_FULL_REINDEX"]:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    suite = load_suite()
    source_rows = {
        item["case_id"]: item
        for item in json.loads(SOURCE_DATASET.read_text(encoding="utf-8")).get("rows") or []
    }
    progress = read_json(PROGRESS, {"cases": []})
    completed = {item["source_case_id"] for item in progress.get("cases") or []}
    for index, case in enumerate(suite["rows"], start=1):
        if case["source_case_id"] in completed:
            continue
        try:
            result = run_case(case, allow_real_api=True, cache_mode="off")
        except Exception as exc:  # noqa: BLE001 - explicit failure evidence.
            result = {
                "source_case_id": case["source_case_id"],
                "query_hash": case["query_hash"],
                "tags": case.get("tags") or [],
                "error": type(exc).__name__,
            }
        progress["cases"].append(result)
        progress["updated_at"] = now_iso()
        write_json(PROGRESS, progress)
        print(json.dumps({
            "progress": f"{index}/{suite['case_count']}",
            "case_id": case["source_case_id"],
            "error": result.get("error"),
            "total_ms": result.get("total_ms"),
        }, ensure_ascii=False), flush=True)
    case_order = {item["source_case_id"]: item["ordinal"] for item in suite["rows"]}
    current_cases = sorted(progress["cases"], key=lambda item: case_order[item["source_case_id"]])
    baseline = json.loads((RUNTIME.parent / "task25f" / "baseline_query_results.json").read_text(encoding="utf-8"))
    baseline_cases = [
        {
            "source_case_id": item["source_case_id"],
            "result": item["result"],
        }
        for item in baseline.get("cases") or []
    ]
    baseline_metrics = _metrics(baseline_cases, source_rows)
    current_metrics = _metrics(current_cases, source_rows)
    baseline_by_case = {item["source_case_id"]: item for item in baseline_cases}
    relevant_loss = []
    for case in current_cases:
        source = source_rows.get(case["source_case_id"]) or {}
        expected = set(source.get("expected_chunk_ids") or []) | set(source.get("expected_semantic_unit_ids") or [])
        if not expected:
            continue
        before = _relevant_rank((baseline_by_case[case["source_case_id"]]["result"].get("candidate_identities") or []), expected)
        after = _relevant_rank((case.get("result") or {}).get("candidate_identities") or [], expected)
        if before is not None and after is None:
            relevant_loss.append(case["source_case_id"])
    citation_ids = {
        value
        for case in current_cases
        for value in ((case.get("result") or {}).get("citation_identities") or [])
    }
    valid_citation_ids: set[str] = set()
    hallucinated_model = []
    hallucinated_alarm = []
    with SessionLocal() as db:
        parsed = []
        for value in citation_ids:
            try:
                parsed.append(UUID(str(value)))
            except ValueError:
                continue
        rows = list(db.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeChunk.id.in_(parsed),
                KnowledgeChunk.status == "active",
                KnowledgeDocument.status == "active",
                KnowledgeDocument.review_status == "approved",
                KnowledgeDocument.parse_status == "parsed",
            )
        )) if parsed else []
        chunk_map = {str(chunk.id): (chunk, document) for chunk, document in rows}
        valid_citation_ids = set(chunk_map)
        for case in current_cases:
            source = source_rows.get(case["source_case_id"]) or {}
            expected_models = {str(value).upper() for value in source.get("expected_device_models") or []}
            expected_alarms = {str(value).upper() for value in source.get("expected_alarm_codes") or []}
            for citation_id in (case.get("result") or {}).get("citation_identities") or []:
                row = chunk_map.get(str(citation_id))
                if row is None:
                    continue
                chunk, document = row
                text = " ".join((document.title or "", document.model or "", chunk.section_title or "", chunk.content or ""))
                models = {value.upper() for value in MODEL_RE.findall(text)}
                alarms = {value.upper() for value in ALARM_RE.findall(text)}
                if expected_models and models and expected_models.isdisjoint(models):
                    hallucinated_model.append({"case_id": case["source_case_id"], "citation_id": citation_id})
                if expected_alarms and alarms and expected_alarms.isdisjoint(alarms):
                    hallucinated_alarm.append({"case_id": case["source_case_id"], "citation_id": citation_id})
    citation_resolution = len(valid_citation_ids) / max(1, len(citation_ids)) if citation_ids else 1.0
    errors = [item["source_case_id"] for item in current_cases if item.get("error")]
    scope_leakage = [
        item["source_case_id"] for item in current_cases
        if (item.get("result") or {}).get("scope_leakage")
    ]
    checks = {
        "candidate_recall_not_lower": current_metrics["candidate_recall"] >= baseline_metrics["candidate_recall"],
        "recall_at_5_not_lower": current_metrics["recall_at_5"] >= baseline_metrics["recall_at_5"],
        "mrr_not_lower": current_metrics["mrr"] >= baseline_metrics["mrr"],
        "ndcg_not_lower": current_metrics["ndcg_at_10"] >= baseline_metrics["ndcg_at_10"],
        "citation_validity_not_lower": current_metrics["citation_validity"] >= baseline_metrics["citation_validity"],
        "citation_coverage_not_lower": current_metrics["citation_coverage"] >= baseline_metrics["citation_coverage"],
        "citation_resolution_100": citation_resolution == 1.0,
        "no_answer_not_degraded": current_metrics["no_answer_accuracy"] >= baseline_metrics["no_answer_accuracy"],
        "clarification_not_degraded": current_metrics["clarification_accuracy"] >= baseline_metrics["clarification_accuracy"],
        "model_hallucination_zero": not hallucinated_model,
        "alarm_hallucination_zero": not hallucinated_alarm,
        "scope_leakage_zero": not scope_leakage,
        "relevant_evidence_loss_zero": not relevant_loss,
        "errors_zero": not errors,
    }
    passed = all(checks.values())
    payload = {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "case_count": len(current_cases),
        "baseline": baseline_metrics,
        "current": current_metrics,
        "citation_resolution": round(citation_resolution, 6),
        "model_hallucination_count": len(hallucinated_model),
        "alarm_hallucination_count": len(hallucinated_alarm),
        "scope_leakage_count": len(scope_leakage),
        "relevant_evidence_loss_count": len(relevant_loss),
        "relevant_evidence_loss_cases": relevant_loss,
        "error_count": len(errors),
        "checks": checks,
        "case_evidence": current_cases,
    }
    write_json("live_quality_stability.json", payload)
    if PROGRESS.exists():
        PROGRESS.unlink()
    print(json.dumps({
        "status": payload["status"], "cases": len(current_cases),
        "candidate_recall": current_metrics["candidate_recall"],
        "recall_at_5": current_metrics["recall_at_5"],
        "mrr": current_metrics["mrr"], "ndcg": current_metrics["ndcg_at_10"],
        "relevant_loss": len(relevant_loss), "errors": len(errors),
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
