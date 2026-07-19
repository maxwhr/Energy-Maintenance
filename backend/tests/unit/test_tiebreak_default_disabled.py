from app.services.minimax_tiebreak_service import MiniMaxTieBreakService
from tests.minimax_test_helpers import candidate, minimax_settings, understanding


def test_tiebreak_is_disabled_in_default_production_path() -> None:
    service = MiniMaxTieBreakService(settings=minimax_settings(RAG_TIEBREAK_EXPERIMENTAL_ENABLED=False))
    result = service.rerank(
        [candidate("a", content="证据一", rrf=0.5), candidate("b", content="证据二", rrf=0.49)],
        understanding=understanding(),
        allow_real_api=True,
    )
    assert result.diagnostics["called"] is False
    assert result.diagnostics["skipped_reason"] == "DISABLED"

