from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from tests.minimax_test_helpers import minimax_settings


def test_cache_key_changes_when_user_context_changes() -> None:
    service = LLMQueryUnderstandingService(None, settings=minimax_settings())
    signals = QuerySignalExtractionService().extract("通信掉线怎么查")
    first = service.cache_key(
        signals.normalized_query, signals=signals,
        conversation_state={"user_clarifications": ["晚上发生"]},
        model_override="MiniMax-M3",
    )
    second = service.cache_key(
        signals.normalized_query, signals=signals,
        conversation_state={"user_clarifications": ["白天发生"]},
        model_override="MiniMax-M3",
    )
    assert first != second

