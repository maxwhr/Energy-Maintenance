from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def _understand(query: str):
    signals = QuerySignalExtractionService().extract(query)
    assessment = QuestionCompletenessService().assess(signals)
    return DeterministicQueryUnderstandingService().understand(signals=signals, assessment=assessment)


def test_intent_rules_cover_required_domains():
    cases = {
        "为什么逆变器反复重启？": "CAUSE",
        "温度过高应该怎么处理？": "TROUBLESHOOTING",
        "如何更换通信模块？": "PROCEDURE",
        "高压场景检查要注意什么？": "SAFETY",
        "告警代码 2001 是什么意思？": "ALARM",
        "启动设备前需要准备什么？": "PREREQUISITE",
        "处理后怎么确认通信恢复？": "VERIFICATION",
        "RS485通信中断": "COMMUNICATION",
        "设备信息": "GENERAL",
    }
    assert {query: _understand(query).intent for query in cases} == cases


def test_alarm_action_is_troubleshooting_and_requires_alarm_identity():
    result = _understand("这个告警该怎么处理？")
    assert result.intent == "TROUBLESHOOTING"
    assert result.needs_clarification is True
    assert "ALARM_CODE" in result.missing_slots


def test_outer_field_request_and_protocol_tokens_are_deterministic():
    action = _understand("SmartLogger RS485通信中断，现场先查啥？")
    assert action.intent == "TROUBLESHOOTING"
    assert action.needs_clarification is False
    signals = QuerySignalExtractionService().extract("SmartLogger RS485通信中断，现场先查啥？")
    assert signals.alarm_codes == []


def test_conversation_specific_symptom_resolves_generic_ambiguity():
    original = QuerySignalExtractionService().extract("设备没反应")
    clarification = QuerySignalExtractionService().extract("型号是 SmartLogger，现象是通信中断，想了解原因")
    state = {
        "original_query": original.original_query,
        "merged_confirmed_facts": clarification.model_dump(),
    }
    assessment = QuestionCompletenessService().assess(clarification)
    result = DeterministicQueryUnderstandingService().understand(
        signals=clarification,
        assessment=assessment,
        conversation_state=state,
    )
    assert result.needs_clarification is False
    assert result.confirmed_facts["device_models"] == ["SmartLogger"]
