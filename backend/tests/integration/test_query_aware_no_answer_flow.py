from app.services.retrieval_confidence_service import RetrievalConfidenceService
from tests.unit.test_retrieval_confidence import citation
from tests.unit.test_evidence_rerank import understanding
from tests.unit.test_clarification_policy import decision


def test_no_grounded_evidence_returns_insufficient_evidence():
    result = RetrievalConfidenceService().assess(understanding=understanding(), clarification=decision("不存在的告警"), candidates=[], citation=citation(False))
    assert result.status == "INSUFFICIENT_EVIDENCE"
