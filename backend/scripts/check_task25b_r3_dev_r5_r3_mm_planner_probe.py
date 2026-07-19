from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import get_settings
from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService
from task25b_r3_dev_r5_r3_mm_common import MODEL_AB_CASES, ratio, sha256_text, write_once


def main() -> None:
    rows = []
    settings = get_settings()
    extractor = QuerySignalExtractionService()
    service = RetrievalPlanService()
    for case in MODEL_AB_CASES[:20]:
        signals = extractor.extract(case["query"])
        assessment = QuestionCompletenessService().assess(signals)
        understanding = LLMQueryUnderstandingService._deterministic(signals, assessment)
        clarification = ClarificationPolicyService().decide(
            signals=signals, assessment=assessment, understanding=understanding
        )
        plan = service.build(understanding, clarification=clarification)
        query_text = " ".join(item.query for item in plan.query_variants)
        extracted = extractor.extract(query_text)
        expected_anchors = service.INTENT_ANCHORS.get(
            understanding.primary_intent, service.INTENT_ANCHORS["GENERAL"]
        )
        passed = bool(
            plan.query_variants
            and plan.query_variants[0].variant_type == "ORIGINAL"
            and plan.query_variants[0].query == understanding.original_query
            and len(plan.query_variants) <= 4
            and set(extracted.device_models).issubset(set(understanding.device_models))
            and set(extracted.alarm_codes).issubset(set(understanding.alarm_codes))
            and plan.anchor_types == expected_anchors
            and plan.query_weights["ORIGINAL"] == settings.RAG_QUERY_WEIGHT_ORIGINAL
            and plan.query_weights["CANONICAL"] == settings.RAG_QUERY_WEIGHT_CANONICAL
            and plan.query_weights["INTENT_QUERY"] == settings.RAG_QUERY_WEIGHT_INTENT
            and plan.query_weights["CONDITION_QUERY"] == settings.RAG_QUERY_WEIGHT_CONDITION
        )
        rows.append({
            "case_id": case["id"],
            "query_hash": sha256_text(case["query"]),
            "original_preserved": plan.query_variants[0].query == understanding.original_query,
            "query_count": len(plan.query_variants),
            "model_hallucination": len(set(extracted.device_models) - set(understanding.device_models)),
            "alarm_hallucination": len(set(extracted.alarm_codes) - set(understanding.alarm_codes)),
            "anchor_mapping_valid": plan.anchor_types == expected_anchors,
            "weights_from_config": all((
                plan.query_weights["ORIGINAL"] == settings.RAG_QUERY_WEIGHT_ORIGINAL,
                plan.query_weights["CANONICAL"] == settings.RAG_QUERY_WEIGHT_CANONICAL,
                plan.query_weights["INTENT_QUERY"] == settings.RAG_QUERY_WEIGHT_INTENT,
                plan.query_weights["CONDITION_QUERY"] == settings.RAG_QUERY_WEIGHT_CONDITION,
            )),
            "passed": passed,
        })
    passed_cases = sum(row["passed"] for row in rows)
    payload = {
        "task": "Task 25B-R3-DEV-R5-R3-MM deterministic planner probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(rows),
        "passed_cases": passed_cases,
        "original_preservation_ratio": ratio(sum(row["original_preserved"] for row in rows), len(rows)),
        "max_query_count": max(row["query_count"] for row in rows),
        "hallucinated_models": sum(row["model_hallucination"] for row in rows),
        "hallucinated_alarms": sum(row["alarm_hallucination"] for row in rows),
        "anchor_mapping_ratio": ratio(sum(row["anchor_mapping_valid"] for row in rows), len(rows)),
        "weights_from_config_ratio": ratio(sum(row["weights_from_config"] for row in rows), len(rows)),
        "expected_labels_used_by_planner": False,
        "status": "PASSED" if passed_cases == len(rows) else "FAILED",
        "rows": rows,
    }
    write_once("planner_probe.json", payload)
    print(json.dumps({"status": payload["status"], "passed": passed_cases, "cases": len(rows)}))


if __name__ == "__main__":
    main()
