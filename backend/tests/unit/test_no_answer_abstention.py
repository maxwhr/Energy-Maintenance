from app.core.database import SessionLocal
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.retrieval_service import RetrievalService


def test_empty_verified_candidates_abstain():
    with SessionLocal() as db:
        service = RetrievalService(db, allow_real_api=False)
        abstain, reason = service._should_abstain(QueryUnderstandingService().understand("未知告警 X9999"), [])
    assert abstain is True
    assert reason == "no_verified_candidates"

