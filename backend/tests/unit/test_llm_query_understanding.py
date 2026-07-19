import json

from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def inputs(query: str):
    signals = QuerySignalExtractionService().extract(query)
    return signals, QuestionCompletenessService().assess(signals)


def test_llm_schema_retry_then_fallback() -> None:
    calls = []

    def invalid(_: str) -> str:
        calls.append(1)
        return "not-json"

    signals, assessment = inputs("晚上通信老掉线，啥原因")
    result = LLMQueryUnderstandingService(None, model_call=invalid).understand(
        signals=signals, assessment=assessment, enable_llm=True
    )
    assert len(calls) == 1
    assert result.fallback_used is True
    assert result.query_understanding_used is False


def test_llm_hallucinated_model_alarm_and_facts_are_removed() -> None:
    signals, assessment = inputs("通信老掉线，啥原因")
    payload = {
        "intent": "CAUSE",
        "canonical_query": "SUN2000-INVENTED 告警99999的通信掉线原因",
        "requested_information": ["CAUSE"],
        "ambiguity": "PARTIAL",
        "missing_slots": ["DEVICE_MODEL"],
        "needs_clarification": False,
        "clarifying_question": "",
        "confidence": 0.8,
    }
    result = LLMQueryUnderstandingService(None, model_call=lambda _: json.dumps(payload, ensure_ascii=False)).understand(
        signals=signals, assessment=assessment, enable_llm=True
    )
    assert result.device_models == []
    assert result.alarm_codes == []
    assert result.alarm_names == []
    assert result.components == signals.components
    assert result.symptoms == signals.symptoms
    assert "hallucinated_canonical_fact_removed" in result.validation_errors


def test_exact_model_fast_path_does_not_call_llm() -> None:
    signals, assessment = inputs("SUN2000-100KTL-M1 如何检查通信")
    called = []
    result = LLMQueryUnderstandingService(None, model_call=lambda _: called.append(1) or "{}").understand(
        signals=signals, assessment=assessment, enable_llm=True
    )
    assert result.fast_path is True
    assert called == []
