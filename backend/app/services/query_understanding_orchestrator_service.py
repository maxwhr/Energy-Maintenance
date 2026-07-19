from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.query_understanding import (
    AmbiguityInterpretation,
    CompletenessAssessment,
    DeterministicUnderstanding,
    QuerySignals,
    QueryUnderstandingResult,
)
from app.services.ambiguity_option_generator_service import AmbiguityOptionGeneratorService
from app.services.clarification_question_template_service import ClarificationQuestionTemplateService
from app.services.deterministic_query_understanding_service import DeterministicQueryUnderstandingService
from app.services.minimax_ambiguity_resolver_service import MiniMaxAmbiguityResolverService


@dataclass(slots=True)
class QueryUnderstandingOrchestration:
    understanding: QueryUnderstandingResult
    deterministic: DeterministicUnderstanding
    ambiguity_options: list[AmbiguityInterpretation]
    minimax_attempted: bool
    minimax_success: bool


class QueryUnderstandingOrchestratorService:
    """Deterministic production path with an optional, lossless MiniMax selector."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        deterministic: DeterministicQueryUnderstandingService | None = None,
        option_generator: AmbiguityOptionGeneratorService | None = None,
        resolver: MiniMaxAmbiguityResolverService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.deterministic_service = deterministic or DeterministicQueryUnderstandingService()
        self.option_generator = option_generator or AmbiguityOptionGeneratorService()
        self.resolver = resolver or MiniMaxAmbiguityResolverService(settings=self.settings)
        self.templates = ClarificationQuestionTemplateService()

    def understand(
        self,
        *,
        signals: QuerySignals,
        assessment: CompletenessAssessment,
        enable_llm: bool,
        allow_real_api: bool,
        conversation_state: dict | None = None,
    ) -> QueryUnderstandingOrchestration:
        deterministic = self.deterministic_service.understand(
            signals=signals,
            assessment=assessment,
            conversation_state=conversation_state,
        )
        baseline = self.deterministic_service.to_result(
            deterministic=deterministic,
            signals=signals,
            assessment=assessment,
            conversation_state=conversation_state,
        )
        options = self.option_generator.generate(signals=signals, understanding=deterministic)
        baseline.ambiguity_options = [item.canonical_query for item in options]
        baseline.clarifying_question = self.templates.first(deterministic.missing_slots)
        baseline.structured_model_diagnostics.update(
            {
                "ambiguity_candidate_count": len(options),
                "ambiguity_candidate_ids": [item.interpretation_id for item in options],
            }
        )

        should_call = bool(
            enable_llm
            and allow_real_api
            and self.settings.RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED
            and self.resolver.eligible(signals=signals, options=options)
        )
        if not should_call:
            return QueryUnderstandingOrchestration(baseline, deterministic, options, False, False)

        resolution = self.resolver.resolve(
            query=signals.normalized_query,
            options=options,
            allow_real_api=allow_real_api,
        )
        if not resolution.success or resolution.patch is None:
            fallback = baseline.model_copy(deep=True)
            fallback.query_understanding_mode = "SAFE_FALLBACK"
            fallback.fallback_used = True
            fallback.requested_provider = "minimax"
            fallback.actual_provider = "deterministic"
            fallback.provider_fallback = True
            fallback.provider_fallback_reason = resolution.fallback_reason
            fallback.structured_model_diagnostics = {
                **fallback.structured_model_diagnostics,
                "minimax": resolution.diagnostics,
                "success": False,
                "tool_call_count": int(resolution.diagnostics.get("tool_call_count") or 0),
                "latency_ms": float(resolution.diagnostics.get("latency_ms") or 0.0),
                "deterministic_semantics_preserved": True,
            }
            return QueryUnderstandingOrchestration(fallback, deterministic, options, True, False)

        patch = resolution.patch
        selected = [item for item in options if item.interpretation_id in patch.selected_interpretation_ids]
        enhanced = baseline.model_copy(deep=True)
        if len(selected) == 1:
            enhanced.primary_intent = selected[0].intent
            enhanced.canonical_question = selected[0].canonical_query
            enhanced.normalized_semantics["canonical_query"] = selected[0].canonical_query
            enhanced.normalized_semantics["selected_interpretation_id"] = selected[0].interpretation_id
        enhanced.needs_clarification = bool(patch.needs_clarification or len(selected) != 1)
        missing_slots = list(patch.missing_slots)
        if enhanced.needs_clarification and not missing_slots:
            missing_slots = list(deterministic.missing_slots)
        enhanced.missing_information = [
            DeterministicQueryUnderstandingService.SLOT_TO_LEGACY[slot] for slot in missing_slots
        ]
        enhanced.clarifying_question = self.templates.first(missing_slots) if enhanced.needs_clarification else None
        enhanced.confidence = patch.confidence
        enhanced.query_understanding_mode = "MINIMAX_AMBIGUITY_RESOLUTION"
        enhanced.model_provider = "minimax"
        enhanced.model_name = self.settings.RAG_MINIMAX_AMBIGUITY_MODEL
        enhanced.requested_provider = "minimax"
        enhanced.actual_provider = "minimax"
        enhanced.structured_model_diagnostics = {
            **enhanced.structured_model_diagnostics,
            "minimax": resolution.diagnostics,
            "success": True,
            "tool_call_count": int(resolution.diagnostics.get("tool_call_count") or 0),
            "latency_ms": float(resolution.diagnostics.get("latency_ms") or 0.0),
            "selected_interpretation_ids": patch.selected_interpretation_ids,
        }
        return QueryUnderstandingOrchestration(enhanced, deterministic, options, True, True)
