from app.core.config import Settings
from app.services.minimax_ambiguity_resolver_service import MiniMaxAmbiguityResolution
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService


class TimedOutResolver:
    def eligible(self, *, signals, options):
        return True

    def resolve(self, **kwargs):
        return MiniMaxAmbiguityResolution(False, None, "TIMEOUT", {"provider_error_code": "TIMEOUT"})


def test_provider_timeout_is_lossless_and_keeps_template_clarification():
    settings = Settings(
        _env_file=None,
        TASK25B_ALLOW_REAL_API=True,
        RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED=True,
    )
    signals = QuerySignalExtractionService().extract("设备没反应")
    result = QueryUnderstandingOrchestratorService(settings=settings, resolver=TimedOutResolver()).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
        allow_real_api=True,
    ).understanding
    assert result.query_understanding_mode == "SAFE_FALLBACK"
    assert result.actual_provider == "deterministic"
    assert result.needs_clarification is True
    assert result.clarifying_question.startswith("请说明具体表现")
    assert result.structured_model_diagnostics["deterministic_semantics_preserved"] is True
