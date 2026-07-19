from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.minimax_tiebreak_service import MiniMaxTieBreakService
from tests.minimax_test_helpers import FakeStructuredService, candidate, minimax_settings, understanding


def test_tiebreak_failure_preserves_exact_deterministic_order() -> None:
    items = [
        candidate("first", content="通信原因一", rrf=0.51),
        candidate("second", content="通信原因二", rrf=0.50),
    ]
    service = MiniMaxTieBreakService(
        settings=minimax_settings(),
        structured_service=FakeStructuredService(success=False, error_code="TIMEOUT"),
        circuit_breaker=MiniMaxCircuitBreaker(),
    )
    result = service.rerank(items, understanding=understanding(), allow_real_api=True, force=True)
    assert [item.candidate_id for item in result.candidates] == ["first", "second"]
    assert result.diagnostics["fallback_order_preserved"] is True
    assert result.diagnostics["provider_fallback"] is True
