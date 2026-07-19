from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService
from tests.minimax_test_helpers import understanding


def test_retrieval_plan_v2_uses_deterministic_anchors_and_weights() -> None:
    item = understanding("通信老是掉线，啥原因")
    item.primary_intent = "COMMUNICATION"
    signals = QuerySignalExtractionService().extract(item.original_query)
    assessment = QuestionCompletenessService().assess(signals)
    clarification = ClarificationPolicyService().decide(signals=signals, assessment=assessment, understanding=item)
    plan = RetrievalPlanService().build(item, clarification=clarification)
    assert plan.query_variants[0].variant_type == "ORIGINAL"
    assert len(plan.query_variants) <= 5
    assert {
        "COMMUNICATION", "SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "VERIFICATION", "FULL_SECTION"
    } <= set(plan.anchor_types)
    assert plan.anchor_types[-1] == "FULL_SECTION"
    assert plan.query_weights["ORIGINAL"] == 1.0
