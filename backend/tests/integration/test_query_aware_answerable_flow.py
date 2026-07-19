from app.services.retrieval_confidence_service import RetrievalConfidenceService
from tests.unit.test_retrieval_confidence import candidate, citation
from tests.unit.test_evidence_rerank import understanding
from tests.unit.test_clarification_policy import decision


def test_complementary_grounded_evidence_is_answerable():
    result = RetrievalConfidenceService().assess(understanding=understanding(), clarification=decision("通信中断是什么原因"), candidates=[candidate("a", .5, "d1"), candidate("b", .49, "d2")], citation=citation(True))
    assert result.status == "ANSWERABLE"
