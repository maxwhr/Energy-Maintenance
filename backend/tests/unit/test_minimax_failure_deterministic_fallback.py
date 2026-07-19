from app.core.config import Settings
from app.services.minimax_ambiguity_resolver_service import MiniMaxAmbiguityResolution
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService


class FailingResolver:
    def eligible(self, *, signals, options):
        return True

    def resolve(self, **kwargs):
        return MiniMaxAmbiguityResolution(False, None, "TIMEOUT", {"provider_error_code": "TIMEOUT"})


def test_minimax_failure_preserves_deterministic_semantics():
    settings = Settings(
        _env_file=None,
        TASK25B_ALLOW_REAL_API=True,
        RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED=True,
    )
    signals = QuerySignalExtractionService().extract("设备没反应")
    assessment = QuestionCompletenessService().assess(signals)
    service = QueryUnderstandingOrchestratorService(settings=settings, resolver=FailingResolver())
    baseline = service.understand(
        signals=signals, assessment=assessment, enable_llm=False, allow_real_api=False
    ).understanding
    fallback = service.understand(
        signals=signals, assessment=assessment, enable_llm=True, allow_real_api=True
    ).understanding
    semantic_fields = [
        "canonical_question", "primary_intent", "confirmed_facts", "device_models", "alarm_codes",
        "symptoms", "conditions", "requested_information", "missing_information", "needs_clarification",
        "clarifying_question",
    ]
    assert {field: getattr(fallback, field) for field in semantic_fields} == {
        field: getattr(baseline, field) for field in semantic_fields
    }
    assert fallback.query_understanding_mode == "SAFE_FALLBACK"
    assert fallback.provider_fallback is True
