from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models import QueryAwareRetrievalSession, User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.schemas.query_understanding import ClarificationRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService


def test_clarification_merges_confirmed_facts_and_retrieves(monkeypatch) -> None:
    monkeypatch.setenv("TASK25B_ALLOW_REAL_API", "false")
    with SessionLocal() as db:
        user = db.scalar(select(User).order_by(User.created_at))
        service = QueryAwareRetrievalService(db, current_user=user)
        first = service.search(QueryAwareSearchRequest(query="设备没反应", enable_llm=False))
        try:
            second = service.clarify(ClarificationRequest(
                conversation_id=first.conversation_id,
                clarification="型号是 SUN2000-100KTL-M1，通信中断，想了解原因",
                enable_llm=False,
            ))
            assert second.needs_clarification is False
            assert second.original_query == "设备没反应"
            assert second.confirmed_facts["device_models"] == ["SUN2000-100KTL-M1"]
            assert "通信中断" in second.confirmed_facts["symptoms"]
            assert second.diagnostics["original_query_retained"] is True
            assert second.answer_boundary["hypotheses_promoted_to_fact"] is False
        finally:
            db.execute(delete(QueryAwareRetrievalSession).where(
                QueryAwareRetrievalSession.conversation_id == first.conversation_id
            ))
            db.commit()
