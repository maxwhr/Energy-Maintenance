import inspect

from app.services import llm_query_understanding_service


def test_query_understanding_uses_configured_timeout():
    source = inspect.getsource(llm_query_understanding_service.LLMQueryUnderstandingService.understand)
    assert "QUERY_UNDERSTANDING_TIMEOUT_SECONDS" in source
    assert "timeout_seconds=3" not in source
