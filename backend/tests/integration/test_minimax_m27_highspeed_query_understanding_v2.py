from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import FakeStructuredService, minimax_settings, query_patch


def test_m27_highspeed_uses_same_v2_contract_without_fake_thinking_disable() -> None:
    signals = QuerySignalExtractionService().extract("通信老是掉线，啥原因")
    result = LLMQueryUnderstandingService(
        None, settings=minimax_settings(), structured_service=FakeStructuredService(query_patch()),
        circuit_breaker=MiniMaxCircuitBreaker(),
    ).understand(
        signals=signals, assessment=QuestionCompletenessService().assess(signals), enable_llm=True,
        allow_real_api=True, model_override="MiniMax-M2.7-highspeed", probe_mode=True, bypass_cache=True,
    )
    assert result.model_name == "MiniMax-M2.7-highspeed"
    assert MiniMaxAnthropicAdapter._thinking_enabled(result.model_name) is True

