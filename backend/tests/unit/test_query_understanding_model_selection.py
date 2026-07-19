from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from tests.minimax_test_helpers import FakeStructuredService, minimax_settings, query_patch


def test_runtime_deterministic_default_and_explicit_probe_model() -> None:
    signals = QuerySignalExtractionService().extract("通信老是掉线，啥原因")
    assessment = QuestionCompletenessService().assess(signals)
    settings = minimax_settings(RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL="deterministic")
    fake = FakeStructuredService(query_patch())
    service = LLMQueryUnderstandingService(
        None, settings=settings, structured_service=fake, circuit_breaker=MiniMaxCircuitBreaker()
    )
    default = service.understand(signals=signals, assessment=assessment, enable_llm=True, allow_real_api=True)
    probed = service.understand(
        signals=signals, assessment=assessment, enable_llm=True, allow_real_api=True,
        model_override="MiniMax-M2.7-highspeed", probe_mode=True, bypass_cache=True,
    )
    assert default.actual_provider == "deterministic"
    assert fake.requests[0].model == "MiniMax-M2.7-highspeed"
    assert probed.model_name == "MiniMax-M2.7-highspeed"

