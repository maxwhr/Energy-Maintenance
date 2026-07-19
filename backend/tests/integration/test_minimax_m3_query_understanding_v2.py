from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import FakeStructuredService, minimax_settings, query_patch


def test_m3_v2_contract_flows_into_business_understanding() -> None:
    signals = QuerySignalExtractionService().extract("通信老是掉线，啥原因")
    result = LLMQueryUnderstandingService(
        None, settings=minimax_settings(), structured_service=FakeStructuredService(query_patch()),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).understand(
        signals=signals, assessment=QuestionCompletenessService().assess(signals), enable_llm=True,
        allow_real_api=True, model_override="MiniMax-M3", probe_mode=True, bypass_cache=True,
    )
    assert result.model_name == "MiniMax-M3"
    assert result.primary_intent == "COMMUNICATION"
    assert result.retrieval_queries == []

