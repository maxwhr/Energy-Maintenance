from __future__ import annotations

from typing import Any


class MaintenanceFeedbackLoopService:
    """Builds analysis-only feedback without changing ranking, prompts, knowledge, or labels."""

    @staticmethod
    def build(
        *,
        initial_diagnosis: dict[str, Any],
        actual_result: dict[str, Any],
        execution_records: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        user_feedback: str | None,
    ) -> dict[str, Any]:
        match_status = actual_result.get("diagnosis_match_status") or "UNDETERMINED"
        correction_signals: list[str] = []
        if match_status in {"MISMATCHED", "PARTIALLY_MATCHED"}:
            correction_signals.append("diagnosis_mismatch")
        if not citations:
            correction_signals.append("missing_citation")
        if any(item.get("record_type") == "NEW_FINDING" for item in execution_records):
            correction_signals.append("new_field_finding")
        if any(item.get("record_type") == "PART_REPLACEMENT" for item in execution_records):
            correction_signals.append("field_part_replacement")
        return {
            "diagnosis_accuracy_feedback": {
                "match_status": match_status,
                "initial_faults": initial_diagnosis.get("possible_faults") or [],
                "actual_fault_cause": actual_result.get("actual_fault_cause"),
            },
            "retrieval_relevance_feedback": {
                "citation_count": len(citations),
                "field_result_supported": match_status == "MATCHED",
            },
            "sop_usefulness_feedback": {
                "executed_step_records": sum(item.get("record_type") == "STEP_RESULT" for item in execution_records),
                "user_feedback": user_feedback,
            },
            "missing_knowledge_signals": correction_signals,
            "correction_candidates": [],
            "production_effects": {
                "ranking_weights_changed": False,
                "production_prompt_changed": False,
                "formal_knowledge_changed": False,
                "expert_verified_changed": False,
                "benchmark_labels_changed": False,
            },
        }
