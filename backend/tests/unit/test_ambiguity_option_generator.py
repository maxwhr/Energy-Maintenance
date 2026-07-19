from app.services.ambiguity_option_generator_service import AmbiguityOptionGeneratorService
from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def _options(query: str):
    signals = QuerySignalExtractionService().extract(query)
    deterministic = DeterministicQueryUnderstandingService().understand(
        signals=signals, assessment=QuestionCompletenessService().assess(signals)
    )
    return AmbiguityOptionGeneratorService().generate(signals=signals, understanding=deterministic)


def test_no_response_has_four_bounded_domain_candidates():
    options = _options("设备没反应")
    assert [item.interpretation_id for item in options] == ["i0", "i1", "i2", "i3"]
    assert {item.canonical_query for item in options} == {
        "设备无法上电", "设备没有功率输出", "设备平台或手机无法通信", "设备指示灯或显示屏没有显示"
    }
    assert all(len(item.reason_codes) == 1 for item in options)


def test_clear_query_has_no_candidates():
    assert _options("SUN2000 告警代码 2001 是什么意思？") == []
