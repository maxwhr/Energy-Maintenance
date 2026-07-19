from app.core.config import get_settings


def test_configured_query_budget_is_bounded_below_hard_gate():
    settings = get_settings()
    assert settings.RAG_MAX_QUERY_VARIANT_CONCURRENCY <= 3
    assert settings.RAG_SCOPE_BATCH_HYDRATION_ENABLED is True
