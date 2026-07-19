from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def _result(query: str):
    signals = QuerySignalExtractionService().extract(query)
    return DeterministicQueryUnderstandingService().understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
    )


def test_canonicalizes_colloquial_communication_with_conditions():
    result = _result("机器晚上总掉线，白天又好了，怎么查？")
    assert result.canonical_query == "设备夜间通信中断，白天恢复正常，查询可能原因和排查方法"
    assert result.requested_information == ["CAUSE", "ACTION"]


def test_preserves_explicit_model_alarm_and_negation():
    result = _result("SUN2000-50KTL 告警代码 2001，重启后仍无法并网，为什么？")
    assert "SUN2000-50KTL" in result.canonical_query
    assert "2001" in result.canonical_query
    assert "无法" in result.canonical_query
    assert result.confirmed_facts["alarm_codes"] == ["2001"]


def test_no_response_remains_ambiguous():
    result = _result("设备没反应")
    assert "没反应" in result.canonical_query
    assert "不开机" not in result.canonical_query
    assert result.ambiguity == "AMBIGUOUS"
