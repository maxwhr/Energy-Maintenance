from app.repositories.vector_index_repository import VectorIndexRepository


def test_default_vector_verification_has_language_guard():
    params = VectorIndexRepository._default_language_filter().compile().params
    assert "normalized_language" in params.values()
    assert "zh-CN" in params.values()
    assert "is_default_retrieval_language" in params.values()
