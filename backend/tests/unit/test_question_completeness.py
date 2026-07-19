from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def assess(query: str):
    signals = QuerySignalExtractionService().extract(query)
    return QuestionCompletenessService().assess(signals)


def test_generic_no_response_is_ambiguous() -> None:
    result = assess("设备没反应")
    assert result.status == "AMBIGUOUS"
    assert result.ambiguity is True
    assert len(result.ambiguity_options) >= 4


def test_exact_alarm_query_is_clear() -> None:
    result = assess("SUN2000 告警代码 2002 是什么原因")
    assert result.status == "CLEAR"
    assert result.missing_information == []


def test_partial_symptom_retains_missing_model() -> None:
    result = assess("晚上通信中断是什么原因")
    assert result.status == "PARTIALLY_SPECIFIED"
    assert "device_model" in result.missing_information


def test_named_alarm_is_clear_and_does_not_trigger_clarification() -> None:
    result = assess("系统接地异常告警是什么原因")
    assert result.status == "CLEAR"
    assert result.ambiguity is False


def test_specific_source_phrase_with_requested_information_is_retrievable() -> None:
    result = assess("信号受到干扰导致通信受影响，一般是什么原因？")
    assert result.status == "PARTIALLY_SPECIFIED"
