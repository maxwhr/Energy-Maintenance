from app.core.config import Settings
from app.schemas.query_understanding import MiniMaxAmbiguityPatch
from app.services.minimax_ambiguity_resolver_service import MiniMaxAmbiguityResolution
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService


class SelectingResolver:
    def eligible(self, *, signals, options):
        return True

    def resolve(self, **kwargs):
        return MiniMaxAmbiguityResolution(
            True,
            MiniMaxAmbiguityPatch(
                selected_interpretation_ids=["i2"],
                needs_clarification=False,
                missing_slots=[],
                confidence=0.91,
            ),
            None,
            {"structured_success": True, "unknown_interpretation_ids": []},
        )


def test_optional_minimax_can_select_but_not_create_interpretation():
    settings = Settings(
        _env_file=None,
        TASK25B_ALLOW_REAL_API=True,
        RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED=True,
    )
    signals = QuerySignalExtractionService().extract("设备没反应")
    result = QueryUnderstandingOrchestratorService(settings=settings, resolver=SelectingResolver()).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=True,
        allow_real_api=True,
    )
    assert result.understanding.query_understanding_mode == "MINIMAX_AMBIGUITY_RESOLUTION"
    assert result.understanding.primary_intent == "COMMUNICATION"
    assert result.understanding.canonical_question == result.ambiguity_options[2].canonical_query
    assert result.understanding.needs_clarification is False
