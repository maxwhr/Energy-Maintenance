from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def decision(query: str):
    signals = QuerySignalExtractionService().extract(query)
    assessment = QuestionCompletenessService().assess(signals)
    understanding = LLMQueryUnderstandingService._deterministic(signals, assessment)
    return ClarificationPolicyService().decide(signals=signals, assessment=assessment, understanding=understanding)


def test_ambiguous_query_requires_clarification_and_suppresses_repairs() -> None:
    result = decision("设备没反应")
    assert result.status == "CLARIFICATION_REQUIRED"
    assert result.suppress_repair_instructions is True
    assert 1 <= len(result.questions) <= 3


def test_exact_alarm_query_does_not_unnecessarily_clarify() -> None:
    result = decision("SUN2000 告警代码 2002 是什么原因")
    assert result.status == "NO_CLARIFICATION"


def test_high_risk_missing_model_never_returns_unbounded_repair_guidance() -> None:
    result = decision("如何带电拆卸通信模块")
    assert result.status in {"CLARIFICATION_REQUIRED", "CLARIFICATION_RECOMMENDED"}
    assert result.suppress_repair_instructions is True
