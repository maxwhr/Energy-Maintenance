from app.services.clarification_policy_service import ClarificationPolicyService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.retrieval_plan_service import RetrievalPlanService
from tests.minimax_test_helpers import understanding


def test_model_result_does_not_own_retrieval_plan() -> None:
    item = understanding("机器晚上总掉线，白天又好了，怎么查？")
    item.primary_intent = "COMMUNICATION"
    item.canonical_question = "设备夜间通信中断，白天恢复正常"
    item.requested_information = ["CAUSE", "ACTION"]
    item.retrieval_queries = ["模型不应控制此查询"]
    item.retrieval_hypotheses = [{"query": "模型不应控制此假设"}]
    signals = QuerySignalExtractionService().extract(item.original_query)
    assessment = QuestionCompletenessService().assess(signals)
    plan = RetrievalPlanService().build(
        item,
        clarification=ClarificationPolicyService().decide(
            signals=signals, assessment=assessment, understanding=item
        ),
    )
    assert all("模型不应控制" not in variant.query for variant in plan.query_variants)
    assert len(plan.query_variants) <= 5
