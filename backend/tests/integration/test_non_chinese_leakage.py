from uuid import uuid4

from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.retrieval_scope import RetrievalScope


def test_non_chinese_and_unknown_language_are_excluded_at_sql_layer():
    scope = RetrievalScope("s", "pilot", "zh-CN", (uuid4(),), "approved", "active",
                           ("development_engineering_auto",), True, True, "c", "pilot_r2")
    params = [value for item in RetrievalRepository._scope_filters(scope) for value in item.compile().params.values()]
    assert "normalized_language" in params and "zh-CN" in params
    assert scope.include_unknown_language is False
