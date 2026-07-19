from uuid import uuid4

from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import RetrievalScope


def test_chinese_scope_repository_builds_sql_filters():
    scope = RetrievalScope("s", "pilot", "zh-CN", (uuid4(),), "approved", "active",
                           ("development_engineering_auto",), True, True, "c", "pilot_r2")
    expressions = RetrievalRepository._scope_filters(scope)
    params = [value for item in expressions for value in item.compile().params.values()]
    assert "normalized_language" in params and "zh-CN" in params
    assert "approved_for_pilot" in params and "true" in params
    assert any("knowledge_documents.id" in str(item) for item in expressions)
