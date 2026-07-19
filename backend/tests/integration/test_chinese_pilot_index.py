from app.repositories.vector_index_repository import VectorIndexRepository


def test_pilot_filter_requires_chinese_and_explicit_pilot_approval():
    params = VectorIndexRepository._pilot_language_filter().compile().params
    assert "normalized_language" in params.values()
    assert "is_pilot_eligible" in params.values()
    assert "approved_for_pilot" in params.values()
