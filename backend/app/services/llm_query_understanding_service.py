from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models import User
from app.schemas.model_gateway import ModelMessage
from app.schemas.query_understanding import (
    CompletenessAssessment,
    QuerySignals,
    QueryUnderstandingResult,
    QueryUnderstandingV2Patch,
)
from app.schemas.structured_model import StructuredModelRequest
from app.services.minimax_resilience import MiniMaxCircuitBreaker, TTLCache, get_minimax_circuit_breaker
from app.services.query_understanding_merge_service import QueryUnderstandingMergeService
from app.services.structured_model_call_service import StructuredModelCallService


class LLMQueryUnderstandingService:
    """Minimal model contract plus deterministic fact/context merge."""

    PROMPT_VERSION = "task25b_r3_dev_r5_r3_mm_query_understanding_v2"
    SCHEMA_VERSION = "query_understanding_v2"
    _cache: TTLCache[dict] | None = None

    def __init__(
        self,
        db: Session | None,
        *,
        current_user: User | None = None,
        model_call: Callable[[str], str] | None = None,
        structured_service: StructuredModelCallService | None = None,
        circuit_breaker: MiniMaxCircuitBreaker | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.current_user = current_user
        self.model_call = model_call
        self.settings = settings or get_settings()
        self.breaker = circuit_breaker or get_minimax_circuit_breaker(
            cooldown_seconds=self.settings.MINIMAX_CIRCUIT_COOLDOWN_SECONDS
        )
        if self.__class__._cache is None:
            self.__class__._cache = TTLCache(
                max_entries=self.settings.MINIMAX_CACHE_MAX_ENTRIES,
                ttl_seconds=self.settings.MINIMAX_CACHE_TTL_SECONDS,
            )
        transport = None
        if model_call is not None:
            transport = lambda request, _mode: model_call(request.messages[-1].content)
        self.structured = structured_service or StructuredModelCallService(
            settings=self.settings, model_call=transport
        )
        self.merge_service = QueryUnderstandingMergeService()

    def understand(
        self,
        *,
        signals: QuerySignals,
        assessment: CompletenessAssessment,
        enable_llm: bool,
        allow_real_api: bool = False,
        conversation_state: dict[str, Any] | None = None,
        model_override: str | None = None,
        probe_mode: bool = False,
        bypass_cache: bool = False,
    ) -> QueryUnderstandingResult:
        deterministic = self._deterministic(signals, assessment)
        deterministic = self.merge_service.merge(
            deterministic=deterministic,
            signals=signals,
            assessment=assessment,
            patch=None,
            conversation_state=conversation_state,
        )
        if (deterministic.fast_path and not probe_mode) or not enable_llm:
            deterministic.query_understanding_mode = (
                "FAST_PATH" if deterministic.fast_path else "DETERMINISTIC_NORMALIZATION"
            )
            deterministic.structured_model_diagnostics = {
                "called": False,
                "success": False,
                "schema_version": self.SCHEMA_VERSION,
                "fallback_reason": "fast_path" if deterministic.fast_path else "llm_disabled",
            }
            return deterministic

        runtime_model = self._runtime_model(model_override)
        if self.model_call is None and runtime_model == "deterministic":
            deterministic.query_understanding_mode = "DETERMINISTIC_NORMALIZATION"
            deterministic.requested_provider = self.settings.RAG_QUERY_UNDERSTANDING_PROVIDER
            deterministic.actual_provider = "deterministic"
            deterministic.structured_model_diagnostics = {
                "called": False,
                "success": False,
                "schema_version": self.SCHEMA_VERSION,
                "selected_runtime_model": "deterministic",
                "fallback_reason": "runtime_model_not_selected",
            }
            return deterministic

        if self.model_call is None and not probe_mode and not self._requires_minimax(signals, assessment):
            deterministic.query_understanding_mode = "DETERMINISTIC_NORMALIZATION"
            deterministic.structured_model_diagnostics = {
                "called": False,
                "success": False,
                "schema_version": self.SCHEMA_VERSION,
                "fallback_reason": "deterministic_normalization_sufficient",
            }
            return deterministic

        requested_provider = (
            "cloud_openai" if self.model_call is not None
            else self.settings.RAG_QUERY_UNDERSTANDING_PROVIDER.strip().lower()
        )
        cache_key = self.cache_key(
            signals.normalized_query,
            requested_provider=requested_provider,
            signals=signals,
            conversation_state=conversation_state,
            model_override=runtime_model,
        )
        assert self._cache is not None
        cached = None if bypass_cache or probe_mode else self._cache.get(cache_key)
        if cached:
            patch = QueryUnderstandingV2Patch.model_validate(deepcopy(cached))
            result = self.merge_service.merge(
                deterministic=deterministic,
                signals=signals,
                assessment=assessment,
                patch=patch,
                conversation_state=conversation_state,
            )
            self._mark_success(
                result,
                model=runtime_model,
                requested_provider=requested_provider,
                actual_provider="minimax_cache" if self.model_call is None else "test_adapter_cache",
                diagnostics={
                    "called": False,
                    "success": True,
                    "cache_hit": True,
                    "schema_version": self.SCHEMA_VERSION,
                    "prompt_version": self.PROMPT_VERSION,
                },
            )
            return result

        circuit_state = self.breaker.state("query_understanding")
        minimax_ready = bool(
            requested_provider == "minimax"
            and self.settings.MINIMAX_ENABLED
            and self.settings.MINIMAX_API_KEY
            and self.settings.MINIMAX_PROTOCOL.strip().lower() == "anthropic"
            and self.settings.MINIMAX_TOOL_CALL_ENABLED
            and self.settings.MINIMAX_FORCE_TOOL_CHOICE
            and self.settings.MINIMAX_SERVICE_TIER.strip().lower() == "standard"
            and allow_real_api
            and self.settings.TASK25B_ALLOW_REAL_API
        )
        circuit_allowed = probe_mode or self.breaker.allow("query_understanding")
        if self.model_call is None and (not minimax_ready or not circuit_allowed):
            return self._fallback(
                deterministic,
                requested_provider=requested_provider,
                reason="circuit_open" if circuit_state == "OPEN" and not probe_mode else "minimax_not_allowed_or_not_configured",
                called=False,
                diagnostics={},
            )

        provider = "cloud_openai" if self.model_call is not None else "minimax_anthropic"
        model = self.settings.CLOUD_LLM_MODEL if self.model_call is not None else runtime_model
        timeout_seconds = min(
            float(self.settings.RAG_QUERY_UNDERSTANDING_TOTAL_BUDGET_SECONDS),
            float(self.settings.MINIMAX_QUERY_TIMEOUT_SECONDS),
        ) if provider == "minimax_anthropic" else min(
            float(self.settings.RAG_QUERY_UNDERSTANDING_TOTAL_BUDGET_SECONDS),
            float(self.settings.QUERY_UNDERSTANDING_TIMEOUT_SECONDS),
        )
        request = StructuredModelRequest(
            purpose="query_understanding",
            messages=[
                ModelMessage(
                    role="system",
                    content=(
                        "只理解和标准化用户问题，不诊断、不回答、不生成检索计划，不虚构型号、告警或事实。"
                        "意图按首要请求选择：问原因选CAUSE，问排查选TROUBLESHOOTING，问步骤选PROCEDURE；"
                        "仅谈通信且未明确原因或动作时选COMMUNICATION。"
                        "必须调用 submit_query_understanding_v2；所有字段必须出现；不输出普通文本或思维过程。"
                    ),
                ),
                ModelMessage(role="user", content=self._prompt(signals)),
            ],
            response_schema=QueryUnderstandingV2Patch.model_json_schema(),
            schema_name="query_understanding_v2",
            tool_name="submit_query_understanding_v2" if provider == "minimax_anthropic" else None,
            tool_description="提交极简查询理解结果；不得返回实体、检索查询、检索假设或维修内容。",
            temperature=self.settings.MINIMAX_TEMPERATURE if provider == "minimax_anthropic" else 0.0,
            top_p=self.settings.MINIMAX_TOP_P if provider == "minimax_anthropic" else None,
            service_tier=self.settings.MINIMAX_SERVICE_TIER if provider == "minimax_anthropic" else None,
            max_tokens=min(int(self.settings.MINIMAX_QUERY_MAX_TOKENS), 512),
            timeout_seconds=timeout_seconds,
            allow_retry=False,
            provider=provider,
            model=model,
            reasoning_effort="low",
            trace_context={
                "query_hash": cache_key,
                "schema_version": self.SCHEMA_VERSION,
                "probe_mode": probe_mode,
            },
        )
        structured = self.structured.call(request, QueryUnderstandingV2Patch)
        diagnostics = structured.model_dump(mode="json")
        diagnostics.pop("parsed_payload", None)
        diagnostics.update({
            "schema_version": self.SCHEMA_VERSION,
            "prompt_version": self.PROMPT_VERSION,
            "cache_hit": False,
        })
        if provider == "minimax_anthropic":
            self.breaker.record(
                "query_understanding",
                success=structured.success,
                error_code=structured.provider_error_code or (
                    "SCHEMA_VALIDATION_FAILED" if structured.validation_errors else None
                ),
                latency_ms=structured.latency_ms,
                probe_mode=probe_mode,
            )
        if not structured.success or structured.parsed_payload is None:
            return self._fallback(
                deterministic,
                requested_provider=requested_provider,
                reason=structured.provider_error_code or "structured_output_failed",
                called=True,
                diagnostics=diagnostics,
                validation_errors=structured.validation_errors,
            )

        patch = QueryUnderstandingV2Patch.model_validate(structured.parsed_payload)
        diagnostics["model_contract_summary"] = {
            "needs_clarification": patch.needs_clarification,
            "ambiguity": patch.ambiguity,
            "requested_information_count": len(patch.requested_information),
            "missing_slot_count": len(patch.missing_slots),
        }
        result = self.merge_service.merge(
            deterministic=deterministic,
            signals=signals,
            assessment=assessment,
            patch=patch,
            conversation_state=conversation_state,
        )
        self._mark_success(
            result,
            model=model or "test_structured_model",
            requested_provider=requested_provider,
            actual_provider="minimax" if provider == "minimax_anthropic" else "test_adapter",
            diagnostics={"called": True, "success": True, **diagnostics},
        )
        if not bypass_cache and not probe_mode:
            self._cache.set(cache_key, patch.model_dump(mode="json"))
        return result

    def _mark_success(
        self,
        result: QueryUnderstandingResult,
        *,
        model: str,
        requested_provider: str,
        actual_provider: str,
        diagnostics: dict[str, Any],
    ) -> None:
        result.model_provider = "minimax" if actual_provider.startswith("minimax") else actual_provider
        result.model_name = model
        result.prompt_version = self.PROMPT_VERSION
        result.fallback_used = False
        result.query_understanding_used = True
        result.fast_path = False
        result.query_understanding_mode = "MINIMAX_TOOL" if actual_provider.startswith("minimax") else "DETERMINISTIC_NORMALIZATION"
        result.requested_provider = requested_provider
        result.actual_provider = actual_provider
        result.provider_fallback = False
        result.provider_fallback_reason = None
        result.circuit_breaker_state = self.breaker.state("query_understanding")
        result.structured_model_diagnostics = diagnostics

    def _fallback(
        self,
        deterministic: QueryUnderstandingResult,
        *,
        requested_provider: str,
        reason: str,
        called: bool,
        diagnostics: dict[str, Any],
        validation_errors: list[str] | None = None,
    ) -> QueryUnderstandingResult:
        deterministic.fallback_used = True
        deterministic.query_understanding_mode = "SAFE_FALLBACK"
        deterministic.requested_provider = requested_provider
        deterministic.actual_provider = "deterministic"
        deterministic.provider_fallback = True
        deterministic.provider_fallback_reason = reason
        deterministic.circuit_breaker_state = self.breaker.state("query_understanding")
        deterministic.validation_errors.extend(validation_errors or [reason])
        deterministic.structured_model_diagnostics = {
            "called": called,
            "success": False,
            "requested_provider": requested_provider,
            "actual_provider": "deterministic",
            "provider_fallback": True,
            "fallback_reason": reason,
            "circuit_breaker_state": deterministic.circuit_breaker_state,
            "schema_version": self.SCHEMA_VERSION,
            **diagnostics,
        }
        return deterministic

    @classmethod
    def _deterministic(cls, signals: QuerySignals, assessment: CompletenessAssessment) -> QueryUnderstandingResult:
        primary, secondary = cls._intents(signals)
        canonical = cls._canonical(signals)
        fast_path = bool(signals.device_models or signals.alarm_codes or signals.alarm_names) and assessment.status != "AMBIGUOUS"
        if any(term in signals.normalized_query for term in ("安全规定", "安全要求", "操作步骤", "检修步骤")) and assessment.status != "AMBIGUOUS":
            fast_path = True
        return QueryUnderstandingResult(
            request_id=f"qu-{uuid4().hex}",
            original_query=signals.original_query,
            normalized_query=signals.normalized_query,
            canonical_question=canonical,
            primary_intent=primary,
            secondary_intents=secondary,
            confirmed_facts=cls._confirmed_facts(signals),
            normalized_semantics={},
            device_models=signals.device_models,
            product_families=cls._families(signals.device_models),
            equipment_categories=cls._equipment_categories(signals.device_models),
            components=signals.components,
            symptoms=signals.symptoms,
            conditions=[*signals.time_conditions, *signals.operating_states],
            alarm_codes=signals.alarm_codes,
            alarm_names=signals.alarm_names,
            requested_information=signals.requested_information or [primary],
            missing_information=assessment.missing_information,
            ambiguity=assessment.ambiguity,
            ambiguity_options=assessment.ambiguity_options,
            retrieval_hypotheses=[],
            retrieval_queries=[],
            route_hints=["EXACT_KEYWORD"] if fast_path else ["SCOPED_KEYWORD", "RAW_VECTOR", "SEMANTIC_UNIT"],
            needs_clarification=assessment.status in {"AMBIGUOUS", "INSUFFICIENT_INFORMATION"},
            clarifying_question=None,
            confidence=0.98 if fast_path else 0.72 if assessment.status == "PARTIALLY_SPECIFIED" else 0.85,
            completeness_status=assessment.status,
            fast_path=fast_path,
            query_understanding_used=False,
            query_understanding_mode="FAST_PATH" if fast_path else "DETERMINISTIC_NORMALIZATION",
        )

    @staticmethod
    def _confirmed_facts(signals: QuerySignals) -> dict[str, list[str]]:
        return {
            "device_models": list(signals.device_models),
            "alarm_codes": list(signals.alarm_codes),
            "alarm_names": list(signals.alarm_names),
            "components": list(signals.components),
            "symptoms": list(signals.symptoms),
            "conditions": [*signals.time_conditions, *signals.operating_states],
            "numbers": list(signals.numbers),
            "negative_expressions": list(signals.negative_expressions),
            "communication_terms": list(signals.communication_terms),
        }

    @staticmethod
    def _canonical(signals: QuerySignals) -> str:
        value = signals.normalized_query
        replacements = {"咋整": "如何处理", "咋办": "如何处理", "啥原因": "可能原因是什么", "没反应": "没有响应"}
        for source, target in replacements.items():
            value = value.replace(source, target)
        return value

    @staticmethod
    def _intents(signals: QuerySignals) -> tuple[str, list[str]]:
        query = signals.normalized_query
        explicit = (
            ("老是掉线", "COMMUNICATION"), ("这种情况老出现", "CAUSE"),
            ("咋排查处理", "TROUBLESHOOTING"), ("按什么顺序操作", "PROCEDURE"),
            ("注意哪些安全风险", "SAFETY"), ("咋确认真的恢复", "VERIFICATION"),
            ("先满足哪些条件", "PREREQUISITE"),
        )
        explicit_primary = next((intent for phrase, intent in explicit if phrase in query), None)
        found: list[str] = []
        if signals.alarm_codes or signals.alarm_names:
            found.append("ALARM")
        intent_mapping = {
            "ACTION": "TROUBLESHOOTING",
            "ALARM_MEANING": "ALARM",
            "CONFIGURATION": "PROCEDURE",
            "GENERAL_INFORMATION": "GENERAL",
        }
        found.extend(intent_mapping.get(value, value) for value in signals.requested_information)
        if signals.communication_terms:
            found.append("COMMUNICATION")
        if signals.symptoms and not found:
            found.append("DIAGNOSIS")
        if not found:
            found.append("GENERAL")
        priority = [
            "ALARM", "SAFETY", "PREREQUISITE", "VERIFICATION", "CAUSE", "COMPONENT",
            "PROCEDURE", "ACTION", "COMMUNICATION", "DIAGNOSIS", "GENERAL",
        ]
        found = list(dict.fromkeys(found))
        primary = explicit_primary or next((value for value in priority if value in found), found[0])
        secondary = [value for value in found if value != primary]
        return (
            "TROUBLESHOOTING" if primary == "ACTION" else primary,
            ["TROUBLESHOOTING" if value == "ACTION" else value for value in secondary],
        )

    @staticmethod
    def _families(models: list[str]) -> list[str]:
        return QueryUnderstandingMergeService._families(models)

    @staticmethod
    def _equipment_categories(models: list[str]) -> list[str]:
        return QueryUnderstandingMergeService._equipment_categories(models)

    @staticmethod
    def _prompt(signals: QuerySignals) -> str:
        return json.dumps(
            {"query": signals.normalized_query},
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def cache_key(
        self,
        normalized_query: str,
        *,
        requested_provider: str | None = None,
        signals: QuerySignals | None = None,
        conversation_state: dict[str, Any] | None = None,
        model_override: str | None = None,
    ) -> str:
        provider = requested_provider or self.settings.RAG_QUERY_UNDERSTANDING_PROVIDER.strip().lower()
        model = model_override or self._runtime_model(None)
        signal_payload = {
            "confirmed_signals": {
                key: value
                for key, value in (signals.model_dump(mode="json") if signals else {}).items()
                if key not in {"original_query", "normalized_query"} and value
            },
            "context_facts": (conversation_state or {}).get("merged_confirmed_facts") or {},
            "context_clarifications": (conversation_state or {}).get("user_clarifications") or [],
        }
        confirmed_signal_hash = hashlib.sha256(
            json.dumps(signal_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        payload = {
            "provider": provider,
            "model": model,
            "schema_version": self.SCHEMA_VERSION,
            "prompt_version": self.PROMPT_VERSION,
            "normalized_query_hash": hashlib.sha256(normalized_query.encode("utf-8")).hexdigest(),
            "confirmed_signal_hash": confirmed_signal_hash,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _runtime_model(self, model_override: str | None) -> str:
        if model_override:
            return model_override
        if self.model_call is not None:
            return self.settings.CLOUD_LLM_MODEL or "test_structured_model"
        value = self.settings.RAG_QUERY_UNDERSTANDING_RUNTIME_MODEL.strip()
        return value or self.settings.MINIMAX_QUERY_UNDERSTANDING_MODEL

    @staticmethod
    def _requires_minimax(signals: QuerySignals, assessment: CompletenessAssessment) -> bool:
        query = signals.normalized_query
        colloquial = any(term in query for term in (
            "没反应", "不正常", "咋整", "咋办", "啥原因", "老是", "有时候", "怎么回事", "不对劲",
        ))
        mixed = len(signals.requested_information) > 1
        vague = assessment.ambiguity or assessment.status in {"AMBIGUOUS", "INSUFFICIENT_INFORMATION"}
        no_exact_anchor = not (signals.device_models or signals.alarm_codes or signals.alarm_names)
        weak_semantics = no_exact_anchor and not (
            signals.components or signals.symptoms or signals.communication_terms or signals.safety_intent
        )
        return colloquial or mixed or vague or weak_semantics
