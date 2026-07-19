from types import SimpleNamespace

from app.services.retrieval_service import RetrievalService


def test_no_answer_rejects_empty_scoped_candidates():
    service = RetrievalService.__new__(RetrievalService)
    service.settings = SimpleNamespace(RETRIEVAL_ABSTENTION_MIN_SCORE=0.3, RETRIEVAL_ABSTENTION_MIN_MARGIN=0.05)
    analysis = SimpleNamespace(normalized_query="未知告警 X999", device_models=[], fault_codes=["X999"])
    assert service._should_abstain(analysis, []) == (True, "no_verified_candidates")
