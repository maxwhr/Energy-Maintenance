from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models import QueryAwareRetrievalSession, User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService


def test_ambiguous_query_returns_question_without_repair_instructions(monkeypatch) -> None:
    monkeypatch.setenv("TASK25B_ALLOW_REAL_API", "false")
    with SessionLocal() as db:
        user = db.scalar(select(User).order_by(User.created_at))
        result = QueryAwareRetrievalService(db, current_user=user).search(QueryAwareSearchRequest(
            query="设备没反应", enable_llm=False, allow_real_api=False,
        ))
        try:
            assert result.needs_clarification is True
            assert result.conversation_id
            assert result.clarifying_question
            assert result.surfaced_results == []
            assert result.answer_boundary["unsupported_repair_instructions"] == 0
        finally:
            db.execute(delete(QueryAwareRetrievalSession).where(
                QueryAwareRetrievalSession.conversation_id == result.conversation_id
            ))
            db.commit()
