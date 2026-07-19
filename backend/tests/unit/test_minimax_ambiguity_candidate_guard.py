import json

from app.core.config import Settings
from app.schemas.query_understanding import AmbiguityInterpretation
from app.services.minimax_ambiguity_resolver_service import MiniMaxAmbiguityResolverService
from app.services.minimax_resilience import MiniMaxCircuitBreaker
from app.services.structured_model_call_service import StructuredModelCallService


def test_unknown_but_schema_valid_candidate_id_is_rejected():
    settings = Settings(
        _env_file=None,
        TASK25B_ALLOW_REAL_API=True,
        MINIMAX_ENABLED=True,
        RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED=True,
    )
    caller = StructuredModelCallService(
        settings=settings,
        model_call=lambda request, mode: json.dumps({
            "selected_interpretation_ids": ["i3"],
            "needs_clarification": False,
            "missing_slots": [],
            "confidence": 0.9,
        }),
    )
    resolver = MiniMaxAmbiguityResolverService(
        settings=settings, caller=caller, breaker=MiniMaxCircuitBreaker()
    )
    options = [
        AmbiguityInterpretation(
            interpretation_id="i0", intent="TROUBLESHOOTING", canonical_query="设备无法上电",
            required_slots=[], supporting_signals=[], confidence=0.5, reason_codes=["fixed"],
        ),
        AmbiguityInterpretation(
            interpretation_id="i1", intent="COMMUNICATION", canonical_query="设备无法通信",
            required_slots=[], supporting_signals=[], confidence=0.5, reason_codes=["fixed"],
        ),
    ]
    result = resolver.resolve(query="设备没反应", options=options, allow_real_api=True)
    assert result.success is False
    assert result.fallback_reason == "UNKNOWN_INTERPRETATION_ID"
    assert result.diagnostics["unknown_interpretation_ids"] == ["i3"]
