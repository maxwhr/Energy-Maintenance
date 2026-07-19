from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.query_understanding import AmbiguityInterpretation, MiniMaxAmbiguityPatch, QuerySignals
from app.schemas.structured_model import StructuredModelRequest
from app.services.minimax_resilience import MiniMaxCircuitBreaker, get_minimax_circuit_breaker
from app.services.structured_model_call_service import StructuredModelCallService


@dataclass(slots=True)
class MiniMaxAmbiguityResolution:
    success: bool
    patch: MiniMaxAmbiguityPatch | None
    fallback_reason: str | None
    diagnostics: dict[str, Any]


class MiniMaxAmbiguityResolverService:
    """Bounded MiniMax tool call that can only select deterministic candidates."""

    TOOL_NAME = "resolve_query_ambiguity"

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        caller: StructuredModelCallService | None = None,
        breaker: MiniMaxCircuitBreaker | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.caller = caller or StructuredModelCallService(settings=self.settings)
        self.breaker = breaker or get_minimax_circuit_breaker(
            cooldown_seconds=self.settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS
        )

    def eligible(self, *, signals: QuerySignals, options: list[AmbiguityInterpretation]) -> bool:
        if len(options) < 2:
            return False
        confidence_span = max(item.confidence for item in options) - min(item.confidence for item in options)
        focused_symptoms = [item for item in signals.symptoms if item not in {"没反应", "异常", "故障", "告警"}]
        enough_specific_facts = bool(signals.alarm_codes or signals.alarm_names or focused_symptoms)
        return bool(
            confidence_span <= 0.15
            and not enough_specific_facts
            and self.settings.RAG_MINIMAX_AMBIGUITY_TOTAL_BUDGET_SECONDS >= 1.0
            and self.breaker.state("query_understanding") == "CLOSED"
        )

    def resolve(
        self,
        *,
        query: str,
        options: list[AmbiguityInterpretation],
        allow_real_api: bool,
        probe_mode: bool = False,
    ) -> MiniMaxAmbiguityResolution:
        if not allow_real_api or not self.settings.TASK25B_ALLOW_REAL_API:
            return self._failure("real_api_not_allowed", "PROVIDER_UNAVAILABLE")
        if not self.settings.RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED:
            return self._failure("resolver_disabled", "PROVIDER_UNAVAILABLE")
        if not self.breaker.allow("query_understanding"):
            return self._failure("circuit_open", "CIRCUIT_OPEN")

        candidate_payload = [
            {
                "interpretation_id": item.interpretation_id,
                "intent": item.intent,
                "canonical_query": item.canonical_query,
                "required_slots": item.required_slots,
                "supporting_signals": item.supporting_signals,
                "confidence": item.confidence,
            }
            for item in options
        ]
        request = StructuredModelRequest(
            purpose="query_ambiguity_resolution",
            provider="minimax_anthropic",
            model=self.settings.RAG_MINIMAX_AMBIGUITY_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你只能从输入候选ID中选择。不得生成查询、答案、型号、告警、原因、步骤或自由文本。"
                        "无法可靠区分时选择空数组并要求追问。必须调用指定工具。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"query": query, "interpretations": candidate_payload},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
            response_schema=MiniMaxAmbiguityPatch.model_json_schema(),
            schema_name="minimax_ambiguity_patch_v1",
            tool_name=self.TOOL_NAME,
            tool_description="Select at most two supplied interpretation IDs and missing slot enums.",
            temperature=0.0,
            top_p=1.0,
            max_tokens=min(160, int(self.settings.RAG_MINIMAX_AMBIGUITY_MAX_TOKENS)),
            timeout_seconds=min(5.0, float(self.settings.RAG_MINIMAX_AMBIGUITY_TOTAL_BUDGET_SECONDS)),
            allow_retry=False,
            service_tier="standard",
            trace_context={"prompt_version": self.settings.RAG_MINIMAX_AMBIGUITY_PROMPT_VERSION},
        )
        result = self.caller.call(request, MiniMaxAmbiguityPatch)
        self.breaker.record(
            "query_understanding",
            success=result.success,
            error_code=result.provider_error_code or (None if result.success else "SCHEMA_VALIDATION_FAILED"),
            latency_ms=result.latency_ms,
            probe_mode=probe_mode,
        )
        diagnostics = {
            "provider": result.provider,
            "model": result.model,
            "tool_name": result.tool_name,
            "structured_success": result.success,
            "tool_call_count": result.tool_call_count,
            "tool_input_valid": result.tool_input_valid,
            "attempt_count": result.attempt_count,
            "latency_ms": result.latency_ms,
            "provider_status": result.provider_status,
            "provider_error_code": result.provider_error_code,
            "validation_errors": result.validation_errors,
            "prompt_version": self.settings.RAG_MINIMAX_AMBIGUITY_PROMPT_VERSION,
            "thinking_enabled": False,
            "max_tokens": request.max_tokens,
            "candidate_ids": [item.interpretation_id for item in options],
            "request_contains_expected_labels": False,
            "request_contains_expected_ids": False,
        }
        if not result.success or not result.parsed_payload:
            return MiniMaxAmbiguityResolution(
                success=False,
                patch=None,
                fallback_reason=result.provider_error_code or "structured_output_failed",
                diagnostics=diagnostics,
            )
        patch = MiniMaxAmbiguityPatch.model_validate(result.parsed_payload)
        allowed = {item.interpretation_id for item in options}
        unknown = sorted(set(patch.selected_interpretation_ids) - allowed)
        if unknown:
            diagnostics["unknown_interpretation_ids"] = unknown
            return MiniMaxAmbiguityResolution(
                success=False,
                patch=None,
                fallback_reason="UNKNOWN_INTERPRETATION_ID",
                diagnostics=diagnostics,
            )
        diagnostics["unknown_interpretation_ids"] = []
        return MiniMaxAmbiguityResolution(success=True, patch=patch, fallback_reason=None, diagnostics=diagnostics)

    @staticmethod
    def _failure(reason: str, code: str) -> MiniMaxAmbiguityResolution:
        return MiniMaxAmbiguityResolution(
            success=False,
            patch=None,
            fallback_reason=reason,
            diagnostics={
                "structured_success": False,
                "provider_error_code": code,
                "attempt_count": 0,
                "tool_call_count": 0,
                "unknown_interpretation_ids": [],
                "thinking_enabled": False,
            },
        )
