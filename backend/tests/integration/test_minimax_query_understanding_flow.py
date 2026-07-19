from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import FakeStructuredService, minimax_settings, query_patch


def test_minimax_query_understanding_preserves_confirmed_facts_and_separates_hypotheses() -> None:
    if LLMQueryUnderstandingService._cache is not None:
        LLMQueryUnderstandingService._cache.clear()
    signals = QuerySignalExtractionService().extract("通信老是掉线，啥原因")
    result = LLMQueryUnderstandingService(
        None,
        settings=minimax_settings(),
        structured_service=FakeStructuredService(query_patch()),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
        allow_real_api=True,
    )
    assert result.query_understanding_mode == "MINIMAX_TOOL"
    assert result.confirmed_facts["communication_terms"] == signals.communication_terms
    assert result.retrieval_hypotheses == []
    assert result.retrieval_queries == []
    assert result.actual_provider == "minimax"
