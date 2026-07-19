from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import FakeStructuredService, minimax_settings


def test_minimax_query_provider_failure_returns_safe_deterministic_result() -> None:
    signals = QuerySignalExtractionService().extract("机器没反应咋办")
    result = LLMQueryUnderstandingService(
        None,
        settings=minimax_settings(),
        structured_service=FakeStructuredService(success=False, error_code="TIMEOUT"),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
        allow_real_api=True,
    )
    assert result.query_understanding_mode == "SAFE_FALLBACK"
    assert result.actual_provider == "deterministic"
    assert result.confirmed_facts["device_models"] == signals.device_models
