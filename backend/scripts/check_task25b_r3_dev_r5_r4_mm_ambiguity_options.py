from __future__ import annotations

from app.services.ambiguity_option_generator_service import AmbiguityOptionGeneratorService
from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r4_mm_common import AMBIGUITY_CASES, now_iso, ratio, write_once


def main() -> int:
    rows = []
    extractor = QuerySignalExtractionService()
    deterministic_service = DeterministicQueryUnderstandingService()
    generator = AmbiguityOptionGeneratorService()
    completeness = QuestionCompletenessService()
    forbidden = ("expected", "benchmark", "因为", "维修步骤", "处理步骤", "更换后", "答案")
    for index, case in enumerate(AMBIGUITY_CASES, start=1):
        signals = extractor.extract(case["query"])
        deterministic = deterministic_service.understand(
            signals=signals, assessment=completeness.assess(signals)
        )
        options = generator.generate(signals=signals, understanding=deterministic)
        serialized = " ".join(
            [item.canonical_query, *item.supporting_signals, *item.reason_codes] for item in options
        ) if False else " ".join(
            token for item in options for token in [item.canonical_query, *item.supporting_signals, *item.reason_codes]
        )
        rows.append({
            "case": index,
            "query": case["query"],
            "expected_interpretation_term": case["expected"],
            "candidate_count": len(options),
            "candidate_ids": [item.interpretation_id for item in options],
            "candidate_queries": [item.canonical_query for item in options],
            "coverage": any(case["expected"] in item.canonical_query for item in options),
            "bounded": 2 <= len(options) <= 4,
            "knowledge_answer_leakage": any(term.lower() in serialized.lower() for term in forbidden),
            "expected_label_leakage": "expected" in serialized.lower() or "benchmark" in serialized.lower(),
        })
    metrics = {
        "cases": len(rows),
        "correct_interpretation_coverage": ratio(sum(row["coverage"] for row in rows), len(rows)),
        "max_candidates": max(row["candidate_count"] for row in rows),
        "knowledge_answer_leakage": sum(row["knowledge_answer_leakage"] for row in rows),
        "expected_label_leakage": sum(row["expected_label_leakage"] for row in rows),
    }
    checks = {
        "cases_at_least_20": len(rows) >= 20,
        "coverage": metrics["correct_interpretation_coverage"] >= 0.95,
        "max_four": metrics["max_candidates"] <= 4,
        "no_answer_leakage": metrics["knowledge_answer_leakage"] == 0,
        "no_expected_label_leakage": metrics["expected_label_leakage"] == 0,
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "metrics": metrics,
        "checks": checks,
        "rows": rows,
    }
    write_once("ambiguity_options_probe.json", payload)
    print({"status": payload["status"], "metrics": metrics, "failed": [k for k, v in checks.items() if not v]})
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
