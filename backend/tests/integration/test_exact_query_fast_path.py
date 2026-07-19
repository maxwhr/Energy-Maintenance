from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import User
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService


def test_exact_model_query_uses_fast_path_without_external_calls(monkeypatch) -> None:
    monkeypatch.setenv("TASK25B_ALLOW_REAL_API", "false")
    with SessionLocal() as db:
        user = db.scalar(select(User).order_by(User.created_at))
        result = QueryAwareRetrievalService(db, current_user=user).search(QueryAwareSearchRequest(
            query="SUN2000-100KTL-M1 通信参数",
            retrieval_mode="fast",
            enable_llm=True,
            allow_real_api=False,
            persist_result=False,
        ))
        assert result.query_understanding_used is False
        assert result.retrieval_plan.fast_path is True
        assert result.requested_channels == ["EXACT_KEYWORD", "SCOPED_KEYWORD"]
        assert result.rerank_used is True
        assert result.minimax_tiebreak.get("called") is False
        assert result.diagnostics["scope_expanded"] is False
