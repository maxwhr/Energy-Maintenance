from __future__ import annotations

import json
from datetime import datetime, timezone

from app.schemas.query_understanding import QueryUnderstandingV2Patch
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.query_understanding_merge_service import QueryUnderstandingMergeService
from app.services.question_completeness_service import QuestionCompletenessService
from task25b_r3_dev_r5_r3_mm_common import ratio, sha256_text, write_once


SCENARIOS = [
    ("设备掉线", "SUN2000-100KTL-M1，晚上发生", "COMMUNICATION"),
    ("机器没反应", "平台没有数据", "TROUBLESHOOTING"),
    ("告警怎么处理", "告警代码2001", "ALARM"),
    ("风扇异常", "高温时发生，想知道原因", "CAUSE"),
    ("通信中断", "使用RS485，想排查", "TROUBLESHOOTING"),
    ("需要操作", "开始前需要哪些条件", "PREREQUISITE"),
    ("已经处理", "如何确认恢复", "VERIFICATION"),
    ("准备更换通信模块", "关注安全风险", "SAFETY"),
    ("设备离线", "SmartLogger3000，白天恢复", "COMMUNICATION"),
    ("需要停机", "请给操作步骤", "PROCEDURE"),
]


REQUEST_MAP = {
    "CAUSE": ["CAUSE"], "TROUBLESHOOTING": ["ACTION"], "PROCEDURE": ["PROCEDURE"],
    "SAFETY": ["SAFETY"], "ALARM": ["ALARM_MEANING"], "PREREQUISITE": ["PREREQUISITE"],
    "VERIFICATION": ["VERIFICATION"], "COMMUNICATION": ["GENERAL_INFORMATION"],
}


def main() -> None:
    rows = []
    extractor = QuerySignalExtractionService()
    merger = QueryUnderstandingMergeService()
    for index, (original, supplement, intent) in enumerate(SCENARIOS, start=1):
        original_signals = extractor.extract(original)
        supplement_signals = extractor.extract(supplement)
        effective = f"{original} 补充说明：{supplement}"
        signals = extractor.extract(effective)
        assessment = QuestionCompletenessService().assess(signals)
        context_facts = {
            key: list(dict.fromkeys([*(getattr(original_signals, key, []) or []), *(getattr(supplement_signals, key, []) or [])]))
            for key in QueryUnderstandingMergeService.CONTEXT_FACT_KEYS
        }
        result = merger.merge(
            deterministic=LLMQueryUnderstandingService._deterministic(signals, assessment),
            signals=signals,
            assessment=assessment,
            patch=QueryUnderstandingV2Patch.model_validate({
                "intent": intent,
                "canonical_query": effective,
                "requested_information": REQUEST_MAP[intent],
                "ambiguity": "PARTIAL",
                "missing_slots": [],
                "needs_clarification": False,
                "clarifying_question": "",
                "confidence": 0.9,
            }),
            conversation_state={
                "original_query": original,
                "user_clarifications": [supplement],
                "merged_confirmed_facts": context_facts,
            },
        )
        expected_models = set(context_facts.get("device_models") or [])
        expected_alarms = set(context_facts.get("alarm_codes") or [])
        passed = bool(
            result.original_query == original
            and expected_models.issubset(result.device_models)
            and expected_alarms.issubset(result.alarm_codes)
            and result.primary_intent == intent
            and result.retrieval_hypotheses == []
            and result.retrieval_queries == []
        )
        rows.append({
            "case_id": f"ctx-{index:02d}",
            "original_hash": sha256_text(original),
            "supplement_hash": sha256_text(supplement),
            "merged_query_hash": sha256_text(effective),
            "expected_model_count": len(expected_models),
            "actual_model_count": len(result.device_models),
            "expected_alarm_count": len(expected_alarms),
            "actual_alarm_count": len(result.alarm_codes),
            "intent_correct": result.primary_intent == intent,
            "original_preserved": result.original_query == original,
            "passed": passed,
        })
    accuracy = ratio(sum(row["passed"] for row in rows), len(rows))
    payload = {
        "task": "Task 25B-R3-DEV-R5-R3-MM context merge probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(rows),
        "passed_cases": sum(row["passed"] for row in rows),
        "accuracy": accuracy,
        "status": "PASSED" if accuracy >= 0.95 else "FAILED",
        "rows": rows,
    }
    write_once("context_merge_probe.json", payload)
    print(json.dumps({"status": payload["status"], "accuracy": accuracy, "cases": len(rows)}))


if __name__ == "__main__":
    main()
