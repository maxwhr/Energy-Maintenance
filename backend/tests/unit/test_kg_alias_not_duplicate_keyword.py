from tests.unit.test_evidence_rerank import understanding
from tests.unit.test_clarification_policy import decision
from app.services.retrieval_plan_service import RetrievalPlanService


def test_kg_alias_is_disabled_until_real_implementation_exists():
    plan = RetrievalPlanService().build(understanding(), clarification=decision("通信中断是什么原因"))
    assert "KG_ALIAS" not in plan.requested_channels
    assert plan.kg_alias_status == "DISABLED_DUPLICATE_KEYWORD"
