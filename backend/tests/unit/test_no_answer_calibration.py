from tests.unit.test_retrieval_confidence import citation
from tests.unit.test_evidence_rerank import understanding
from tests.unit.test_clarification_policy import decision
from app.services.retrieval_confidence_service import RetrievalConfidenceService


def test_no_valid_candidate_is_no_answer():
    result = RetrievalConfidenceService().assess(understanding=understanding(), clarification=decision("通信中断是什么原因"), candidates=[], citation=citation(False))
    assert result.status == "INSUFFICIENT_EVIDENCE"
