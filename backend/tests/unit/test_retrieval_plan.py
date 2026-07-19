from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService


def build(query: str):
    signals = QuerySignalExtractionService().extract(query)
    assessment = QuestionCompletenessService().assess(signals)
    understanding = LLMQueryUnderstandingService._deterministic(signals, assessment)
    clarification = ClarificationPolicyService().decide(
        signals=signals, assessment=assessment, understanding=understanding
    )
    return RetrievalPlanService().build(understanding, clarification=clarification)


def test_original_query_is_always_retained_and_variants_are_bounded() -> None:
    plan = build("通信中断是什么原因，如何处理并验证恢复")
    assert plan.query_variants[0].variant_type == "ORIGINAL"
    assert plan.query_variants[0].query == "通信中断是什么原因，如何处理并验证恢复"
    assert len(plan.query_variants) <= 5
    assert plan.required_scope == "chinese_engineering_pilot_r2"


def test_exact_model_uses_fast_path_channels() -> None:
    plan = build("SUN2000-100KTL-M1 通信参数")
    assert plan.fast_path is True
    assert plan.requested_channels == ["EXACT_KEYWORD", "SCOPED_KEYWORD"]


def test_vector_channels_use_at_most_original_and_canonical_queries() -> None:
    plan = build("通信中断是什么原因，如何处理并验证恢复")
    assert len(plan.channel_queries["RAW_VECTOR"]) <= 3
    assert len(plan.channel_queries["SEMANTIC_UNIT"]) <= 3
    assert len(plan.channel_queries["SCOPED_KEYWORD"]) >= len(plan.channel_queries["RAW_VECTOR"])
