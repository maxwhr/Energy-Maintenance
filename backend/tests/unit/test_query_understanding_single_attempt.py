from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def test_query_understanding_uses_one_structured_attempt() -> None:
    calls = []
    signals = QuerySignalExtractionService().extract("通信老是掉线，啥原因")
    result = LLMQueryUnderstandingService(None, model_call=lambda _: calls.append(1) or "not-json").understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
    )
    assert len(calls) == 1
    assert result.fallback_used is True

