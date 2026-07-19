from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.minimax_tiebreak_service import MiniMaxTieBreakService
from tests.minimax_test_helpers import FakeStructuredService, candidate, minimax_settings, understanding


def test_minimax_tiebreak_reorders_only_supplied_candidates_and_appends_missing_ids() -> None:
    items = [
        candidate("a", content="通信原因 A", rrf=0.51),
        candidate("b", content="通信原因 B", rrf=0.50),
        candidate("c", content="通信原因 C", rrf=0.49),
    ]
    fake = FakeStructuredService({
        "ordered_candidate_ids": ["c1", "c0"],
        "scores": [
            {"candidate_id": "c1", "support": 0.9, "intent_match": 0.9, "contradiction": False},
            {"candidate_id": "c0", "support": 0.8, "intent_match": 0.8, "contradiction": False},
        ],
        "needs_clarification": False,
    })
    result = MiniMaxTieBreakService(
        settings=minimax_settings(), structured_service=fake, circuit_breaker=MiniMaxCircuitBreaker()
    ).rerank(items, understanding=understanding(), allow_real_api=True, force=True)
    assert [item.candidate_id for item in result.candidates] == ["b", "a", "c"]
    assert result.diagnostics["candidate_additions"] == 0
    assert result.diagnostics["candidate_removals"] == 0
