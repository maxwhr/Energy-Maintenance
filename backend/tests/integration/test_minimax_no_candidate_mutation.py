from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.minimax_tiebreak_service import MiniMaxTieBreakService
from tests.minimax_test_helpers import FakeStructuredService, candidate, minimax_settings, understanding


def test_minimax_tiebreak_does_not_mutate_candidate_content_or_source() -> None:
    items = [candidate("a", content="原始证据 A", rrf=0.5), candidate("b", content="原始证据 B", rrf=0.49)]
    snapshot = {item.candidate_id: (item.content, set(item.source_channels), list(item.source_chunk_ids)) for item in items}
    fake = FakeStructuredService({
        "ordered_candidate_ids": ["c1", "c0"],
        "scores": [
            {"candidate_id": "c1", "support": 1, "intent_match": 1, "contradiction": False},
            {"candidate_id": "c0", "support": 0.5, "intent_match": 0.5, "contradiction": False},
        ], "needs_clarification": False,
    })
    result = MiniMaxTieBreakService(
        settings=minimax_settings(), structured_service=fake, circuit_breaker=MiniMaxCircuitBreaker()
    ).rerank(items, understanding=understanding(), allow_real_api=True, force=True)
    assert all((item.content, item.source_channels, item.source_chunk_ids) == snapshot[item.candidate_id] for item in result.candidates)
