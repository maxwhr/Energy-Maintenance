from app.core.config import Settings
from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService
from app.services.retrieval_plan_service import RetrievalPlanService


def test_r5_planner_remains_deterministic_and_bounded_to_five_queries():
    signals = QuerySignalExtractionService().extract("SUN2000-50KTL 夜间通信掉线，白天正常，为什么？")
    assessment = QuestionCompletenessService().assess(signals)
    understanding = QueryUnderstandingOrchestratorService(settings=Settings(_env_file=None)).understand(
        signals=signals, assessment=assessment, enable_llm=False, allow_real_api=False
    ).understanding
    decision = ClarificationPolicyService().decide(
        signals=signals, assessment=assessment, understanding=understanding
    )
    plan = RetrievalPlanService().build(understanding, clarification=decision)
    assert len(plan.query_variants) <= 5
    assert {item.variant_type for item in plan.query_variants} <= {
        "ORIGINAL", "CANONICAL", "SYMPTOM_QUERY", "REQUEST_QUERY", "CONDITION_QUERY"
    }
    assert plan.anchor_types == [
        "CAUSE", "SYMPTOM", "ALARM", "FULL_SECTION"
    ]
    assert all("MiniMax" not in item.query for item in plan.query_variants)
