from app.schemas.query_understanding import QueryUnderstandingV2Patch
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.query_understanding_merge_service import QueryUnderstandingMergeService
from app.services.question_completeness_service import QuestionCompletenessService


def test_context_supplement_is_merged_before_planning() -> None:
    signals = QuerySignalExtractionService().extract("晚上掉线，怎么查")
    assessment = QuestionCompletenessService().assess(signals)
    result = QueryUnderstandingMergeService().merge(
        deterministic=LLMQueryUnderstandingService._deterministic(signals, assessment),
        signals=signals,
        assessment=assessment,
        patch=QueryUnderstandingV2Patch.model_validate({
            "intent": "COMMUNICATION", "canonical_query": "设备夜间掉线排查",
            "requested_information": ["ACTION"], "ambiguity": "PARTIAL",
            "missing_slots": [], "needs_clarification": False,
            "clarifying_question": "", "confidence": 0.9,
        }),
        conversation_state={"merged_confirmed_facts": {"device_models": ["SmartLogger3000"]}},
    )
    assert result.confirmed_facts["device_models"] == ["SmartLogger3000"]
    assert result.canonical_question == "设备夜间掉线排查"

