from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def test_malformed_llm_output_falls_back_without_fabricating_facts() -> None:
    signals = QuerySignalExtractionService().extract("通信总是掉线，啥原因")
    assessment = QuestionCompletenessService().assess(signals)
    result = LLMQueryUnderstandingService(None, model_call=lambda _: "malformed").understand(
        signals=signals, assessment=assessment, enable_llm=True
    )
    assert result.fallback_used is True
    assert result.device_models == []
    assert result.alarm_codes == []
    assert result.primary_intent == "CAUSE"
