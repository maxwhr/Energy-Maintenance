from tests.unit.test_retrieval_confidence import candidate, citation
from tests.unit.test_evidence_rerank import understanding
from tests.unit.test_clarification_policy import decision
from app.services.retrieval_confidence_service import RetrievalConfidenceService


def test_explicit_multiple_models_trigger_real_conflict():
    u = understanding(); u.device_models = ["SUN2000-A", "SUN2000-B"]
    items = [candidate("a", .5), candidate("b", .499)]; items[0].exact_model_match = items[1].exact_model_match = True
    result = RetrievalConfidenceService().assess(understanding=u, clarification=decision("通信中断是什么原因"), candidates=items, citation=citation(True))
    assert result.status == "MULTIPLE_POSSIBILITIES" and result.entity_conflicts
