from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import minimax_settings


def test_unavailable_minimax_routes_directly_to_deterministic_fallback() -> None:
    settings = minimax_settings(TASK25B_ALLOW_REAL_API=False)
    signals = QuerySignalExtractionService().extract("机器没反应咋办")
    result = LLMQueryUnderstandingService(
        None, settings=settings, circuit_breaker=MiniMaxCircuitBreaker()
    ).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
        allow_real_api=True,
    )
    assert result.requested_provider == "minimax"
    assert result.actual_provider == "deterministic"
    assert result.query_understanding_mode == "SAFE_FALLBACK"
