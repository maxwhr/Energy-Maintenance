from app.services.minimax_resilience import MiniMaxCircuitBreaker


def test_query_and_tiebreak_circuits_are_independent() -> None:
    breaker = MiniMaxCircuitBreaker(cooldown_seconds=60)
    for _ in range(5):
        breaker.record("query_understanding", success=False, error_code="TIMEOUT")
    assert breaker.state("query_understanding") == "OPEN"
    assert breaker.state("tiebreak") == "CLOSED"
    assert breaker.allow("query_understanding") is False
