from app.core.config import get_settings


def test_retrieval_budget_and_external_concurrency_are_bounded():
    settings = get_settings()
    assert settings.RETRIEVAL_TOTAL_BUDGET_MS <= 3500
    assert settings.EMBEDDING_MAX_CONCURRENCY <= 2

