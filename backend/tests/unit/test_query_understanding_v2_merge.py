from app.schemas.query_understanding import QueryUnderstandingV2Patch
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.query_understanding_merge_service import QueryUnderstandingMergeService
from app.services.question_completeness_service import QuestionCompletenessService


def test_v2_merge_preserves_context_and_deterministic_entities() -> None:
    signals = QuerySignalExtractionService().extract("晚上通信掉线，怎么查")
    assessment = QuestionCompletenessService().assess(signals)
    deterministic = LLMQueryUnderstandingService._deterministic(signals, assessment)
    patch = QueryUnderstandingV2Patch.model_validate({
        "intent": "COMMUNICATION",
        "canonical_query": "设备夜间通信中断，查询排查方法",
        "requested_information": ["ACTION"],
        "ambiguity": "PARTIAL",
        "missing_slots": [],
        "needs_clarification": False,
        "clarifying_question": "",
        "confidence": 0.9,
    })
    result = QueryUnderstandingMergeService().merge(
        deterministic=deterministic,
        signals=signals,
        assessment=assessment,
        patch=patch,
        conversation_state={
            "original_query": "设备通信掉线",
            "merged_confirmed_facts": {"device_models": ["SUN2000-100KTL-M1"]},
        },
    )
    assert result.device_models == ["SUN2000-100KTL-M1"]
    assert result.confirmed_facts["device_models"] == ["SUN2000-100KTL-M1"]
    assert result.retrieval_hypotheses == []
    assert result.retrieval_queries == []

