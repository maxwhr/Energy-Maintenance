from app.core.config import Settings
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService


class CountingResolver:
    calls = 0

    def eligible(self, *, signals, options):
        return len(options) >= 2

    def resolve(self, **kwargs):
        self.calls += 1
        raise AssertionError("clear query must never call MiniMax")


def test_no_llm_on_clear_query_even_when_optional_resolver_enabled():
    resolver = CountingResolver()
    settings = Settings(
        _env_file=None,
        TASK25B_ALLOW_REAL_API=True,
        RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED=True,
    )
    signals = QuerySignalExtractionService().extract("SUN2000-50KTL 告警代码 2001 是什么意思？")
    result = QueryUnderstandingOrchestratorService(settings=settings, resolver=resolver).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
        allow_real_api=True,
    )
    assert resolver.calls == 0
    assert result.minimax_attempted is False
    assert result.understanding.query_understanding_mode == "FAST_PATH"
