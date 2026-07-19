from app.core.config import Settings
from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService
from app.services.retrieval_plan_service import RetrievalPlanService


def test_deterministic_understanding_reaches_planner_without_external_call():
    signals = QuerySignalExtractionService().extract("机器晚上总掉线，白天又好了，怎么查？")
    assessment = QuestionCompletenessService().assess(signals)
    orchestration = QueryUnderstandingOrchestratorService(settings=Settings(_env_file=None)).understand(
        signals=signals, assessment=assessment, enable_llm=False, allow_real_api=False
    )
    decision = ClarificationPolicyService().decide(
        signals=signals, assessment=assessment, understanding=orchestration.understanding
    )
    plan = RetrievalPlanService().build(orchestration.understanding, clarification=decision)
    assert orchestration.understanding.primary_intent == "TROUBLESHOOTING"
    assert orchestration.understanding.structured_model_diagnostics["external_call_count"] == 0
    assert decision.status == "NO_CLARIFICATION"
    assert [item.variant_type for item in plan.query_variants] == [
        "ORIGINAL", "CANONICAL", "SYMPTOM_QUERY", "REQUEST_QUERY", "CONDITION_QUERY"
    ]
