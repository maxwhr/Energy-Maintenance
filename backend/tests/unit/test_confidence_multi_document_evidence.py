from tests.unit.test_retrieval_confidence import candidate, citation
from tests.unit.test_evidence_rerank import understanding
from tests.unit.test_clarification_policy import decision
from app.services.retrieval_confidence_service import RetrievalConfidenceService


def test_multiple_documents_are_not_automatically_conflicting():
    result = RetrievalConfidenceService().assess(understanding=understanding(), clarification=decision("通信中断是什么原因"), candidates=[candidate("a", .5, "d1"), candidate("b", .495, "d2")], citation=citation(True))
    assert result.status == "ANSWERABLE" and not result.entity_conflicts
