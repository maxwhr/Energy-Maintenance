from app.repositories.retrieval_repository import RetrievalRepository


def test_keyword_default_excludes_missing_and_alternate_language():
    params = RetrievalRepository._default_language_filter().compile().params.values()
    assert "normalized_language" in params and "zh-CN" in params
    assert "is_default_retrieval_language" in params and "true" in params
