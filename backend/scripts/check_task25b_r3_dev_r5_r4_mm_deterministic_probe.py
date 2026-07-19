from __future__ import annotations

import time

from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r4_mm_common import DETERMINISTIC_CASES, now_iso, p95, ratio, write_once


def main() -> int:
    rows = []
    service = DeterministicQueryUnderstandingService()
    extractor = QuerySignalExtractionService()
    completeness = QuestionCompletenessService()
    for index, case in enumerate(DETERMINISTIC_CASES, start=1):
        started = time.perf_counter()
        signals = extractor.extract(case["query"])
        deterministic = service.understand(signals=signals, assessment=completeness.assess(signals))
        result = service.to_result(
            deterministic=deterministic, signals=signals, assessment=completeness.assess(signals)
        )
        latency = (time.perf_counter() - started) * 1000
        actual_models = set(result.device_models)
        actual_alarms = set(result.alarm_codes)
        expected_models = set(signals.device_models)
        expected_alarms = set(signals.alarm_codes)
        rows.append({
            "case": index,
            "query": case["query"],
            "expected_intent": case["intent"],
            "actual_intent": deterministic.intent,
            "intent_correct": deterministic.intent == case["intent"],
            "canonical_query": deterministic.canonical_query,
            "required_terms": case["terms"],
            "canonicalization_correct": all(term in deterministic.canonical_query for term in case["terms"]),
            "expected_clarification": case["clarify"],
            "actual_clarification": deterministic.needs_clarification,
            "clarification_correct": deterministic.needs_clarification == case["clarify"],
            "hallucinated_models": sorted(actual_models - expected_models),
            "hallucinated_alarms": sorted(actual_alarms - expected_alarms),
            "external_call_count": result.structured_model_diagnostics["external_call_count"],
            "latency_ms": round(latency, 3),
        })
    metrics = {
        "cases": len(rows),
        "intent_accuracy": ratio(sum(row["intent_correct"] for row in rows), len(rows)),
        "canonicalization_accuracy": ratio(sum(row["canonicalization_correct"] for row in rows), len(rows)),
        "clarification_accuracy": ratio(sum(row["clarification_correct"] for row in rows), len(rows)),
        "hallucinated_models": sum(len(row["hallucinated_models"]) for row in rows),
        "hallucinated_alarms": sum(len(row["hallucinated_alarms"]) for row in rows),
        "external_calls": sum(row["external_call_count"] for row in rows),
        "p95_ms": p95([row["latency_ms"] for row in rows]),
    }
    checks = {
        "cases_at_least_50": len(rows) >= 50,
        "intent_accuracy": metrics["intent_accuracy"] >= 0.95,
        "canonicalization": metrics["canonicalization_accuracy"] >= 0.90,
        "model_hallucination_zero": metrics["hallucinated_models"] == 0,
        "alarm_hallucination_zero": metrics["hallucinated_alarms"] == 0,
        "external_calls_zero": metrics["external_calls"] == 0,
        "p95_within_100_ms": metrics["p95_ms"] <= 100.0,
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "metrics": metrics,
        "checks": checks,
        "rows": rows,
    }
    write_once("deterministic_probe.json", payload)
    print({"status": payload["status"], "metrics": metrics, "failed": [k for k, v in checks.items() if not v]})
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
