import inspect

from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_tiebreak_service import MiniMaxTieBreakService


def test_query_and_tiebreak_do_not_chain_to_stepfun() -> None:
    source = inspect.getsource(LLMQueryUnderstandingService.understand) + inspect.getsource(MiniMaxTieBreakService.rerank)
    assert "StepFun" not in source
    assert "RAG_REQUEST_LEVEL_PROVIDER_FALLBACK_ENABLED" not in source
