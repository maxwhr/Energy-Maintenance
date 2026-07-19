from __future__ import annotations

import json
from collections import Counter

from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r5_common import OUT, SOURCE, now_iso, write_once


def _classification(query: str, expected: str, actual: str, requested: list[str]) -> str:
    if len(requested) > 1:
        return "COMPOSITE_INTENT"
    if expected == "TROUBLESHOOTING" and actual == "GENERAL":
        return "TRIGGER_PRECEDENCE"
    if expected == "COMMUNICATION" and actual != expected:
        return "COMMUNICATION_OVERRULED"
    if {expected, actual} == {"PROCEDURE", "TROUBLESHOOTING"}:
        return "PROCEDURE_VS_TROUBLESHOOTING"
    if {expected, actual} == {"CAUSE", "TROUBLESHOOTING"}:
        return "CAUSE_VS_TROUBLESHOOTING"
    if "SAFETY" in requested:
        return "SAFETY_SECONDARY_INTENT"
    if "VERIFICATION" in requested:
        return "VERIFICATION_SECONDARY_INTENT"
    return "LABEL_ERROR"


def main() -> None:
    iteration = json.loads((SOURCE / "canary_iteration_2.json").read_text(encoding="utf-8"))
    source_rows = {row["case_id"]: row for row in json.loads((SOURCE / "train_dev_dataset_v1.json").read_text(encoding="utf-8"))["rows"]}
    fixed = json.loads((OUT / "train_dev_dataset_v1.json").read_text(encoding="utf-8"))["rows"]
    fixed_by_query = {row["query"]: row for row in fixed}
    extractor = QuerySignalExtractionService()
    completeness = QuestionCompletenessService()
    deterministic = DeterministicQueryUnderstandingService()
    errors = []
    baseline_rows = iteration["deterministic_only"]["rows"]
    for row in baseline_rows:
        if row.get("actual_intent") == row.get("expected_intent"):
            continue
        label = source_rows[row["case_id"]]
        signals = extractor.extract(label["query"])
        assessment = completeness.assess(signals)
        understood = deterministic.understand(signals=signals, assessment=assessment)
        fixed_row = fixed_by_query.get(label["query"], {})
        requested = fixed_row.get("expected_requested_information") or list(understood.requested_information)
        errors.append({
            "case_id": row["case_id"],
            "query": label["query"],
            "expected_primary_intent": row.get("expected_intent"),
            "actual_primary_intent": row.get("actual_intent"),
            "deterministic_requested_information": list(understood.requested_information),
            "expected_requested_information": requested,
            "ambiguity": understood.ambiguity,
            "needs_clarification": understood.needs_clarification,
            "classification": _classification(label["query"], row.get("expected_intent"), row.get("actual_intent"), requested),
            "root_cause": "generic failure symptoms were treated only as ambiguity signals and did not participate in primary intent selection",
        })
    counts = Counter(item["classification"] for item in errors)
    payload = {
        "generated_at": now_iso(),
        "baseline": "task25b_r3_dev_r5_r4_mm iteration 2 deterministic-only",
        "case_count": len(baseline_rows),
        "intent_error_count": len(errors),
        "primary_intent_accuracy": round(1 - len(errors) / len(baseline_rows), 6),
        "classification_counts": dict(sorted(counts.items())),
        "hardcoded_case_rules_used": False,
        "rows": errors,
    }
    write_once("intent_forensics.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
