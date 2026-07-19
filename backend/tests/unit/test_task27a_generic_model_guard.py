from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService
from tests.minimax_test_helpers import candidate, understanding


def test_generic_sun2000_query_does_not_reject_specific_scope_model() -> None:
    query = understanding("SUN2000 检修下电后应等待多久？")
    query.device_models = ["SUN2000"]
    item = candidate(
        "specific-manual",
        content="SUN2000-330KTL-H1 检修下电后等待15min。",
        rrf=0.5,
    )

    result = PreRerankHardGuardService().apply([item], understanding=query)

    assert result.candidates == [item]
    assert result.diagnostics["removed_count"] == 0


def test_specific_sun2000_model_still_rejects_explicit_other_model() -> None:
    query = understanding("SUN2000-33KTL 如何安装？")
    query.device_models = ["SUN2000-33KTL"]
    item = candidate(
        "wrong-model",
        content="SUN2000-330KTL-H1 安装说明。",
        rrf=0.5,
    )

    result = PreRerankHardGuardService().apply([item], understanding=query)

    assert result.candidates == []
    assert result.diagnostics["removals"][0]["reason"] == "EXPLICIT_WRONG_MODEL"


def test_generic_sun2000_query_does_not_enable_exact_model_channel() -> None:
    signals = QuerySignalExtractionService().extract("SUN2000 检修下电后应等待多久？")
    assessment = QuestionCompletenessService().assess(signals)
    query = LLMQueryUnderstandingService._deterministic(signals, assessment)
    clarification = ClarificationPolicyService().decide(
        signals=signals,
        assessment=assessment,
        understanding=query,
    )

    plan = RetrievalPlanService().build(query, clarification=clarification)

    assert "EXACT_KEYWORD" not in plan.requested_channels
