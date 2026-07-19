from app.core.database import SessionLocal
from app.repositories.retrieval_repository import RetrievalRepository


def test_retrieval_filters_exclude_unapproved_by_contract():
    with SessionLocal() as db:
        candidates = RetrievalRepository(db).list_knowledge_candidates(keywords=["逆变器"], device_type="pv_inverter", candidate_limit=20)
        assert all(document.review_status == "approved" and document.status == "active" and chunk.status == "active" for chunk, document in candidates)
