from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.query_understanding import (
    CompletenessAssessment,
    QuerySignals,
    QueryUnderstandingResult,
    QueryUnderstandingV2Patch,
)
from app.services.query_signal_extraction_service import QuerySignalExtractionService


class QueryUnderstandingMergeService:
    """Merge model-owned semantics without allowing it to overwrite explicit facts."""

    CONTEXT_FACT_KEYS = (
        "device_models", "alarm_codes", "alarm_names", "components", "time_conditions",
        "operating_states", "numbers", "negative_expressions", "communication_terms",
        "symptoms", "requested_information",
    )
    CONTEXT_SCALAR_FACT_KEYS = (
        "manufacturer", "product_family", "model", "model_original", "alarm_code",
        "fault_type", "maintenance_intent", "safety_risk",
    )
    SLOT_TO_LEGACY = {
        "DEVICE_MODEL": "device_model",
        "ALARM_CODE": "specific_symptom_or_alarm_code",
        "SPECIFIC_SYMPTOM": "specific_symptom_or_alarm_code",
        "COMPONENT": "component",
        "COMMUNICATION_METHOD": "communication_method",
        "OCCURRENCE_CONDITION": "occurrence_condition",
        "REQUESTED_ACTION": "requested_information",
    }

    def merge(
        self,
        *,
        deterministic: QueryUnderstandingResult,
        signals: QuerySignals,
        assessment: CompletenessAssessment,
        patch: QueryUnderstandingV2Patch | None,
        conversation_state: dict[str, Any] | None = None,
    ) -> QueryUnderstandingResult:
        merged_signals = self.merge_signals(signals, conversation_state=conversation_state)
        result = deterministic.model_copy(deep=True)
        result.original_query = str((conversation_state or {}).get("original_query") or signals.original_query)
        result.normalized_query = signals.normalized_query
        self._apply_explicit_facts(result, merged_signals)

        if patch is None:
            result.normalized_semantics = {
                "canonical_query": result.canonical_question,
                "symptoms": list(merged_signals.symptoms),
                "components": list(merged_signals.components),
                "conditions": [*merged_signals.time_conditions, *merged_signals.operating_states],
                "requested_information": list(result.requested_information),
            }
            result.retrieval_hypotheses = []
            result.retrieval_queries = []
            return result

        canonical = patch.canonical_query.strip()
        canonical_signals = QuerySignalExtractionService().extract(canonical)
        if self._adds_explicit_entity(canonical_signals, merged_signals):
            canonical = deterministic.canonical_question
            result.validation_errors.append("hallucinated_canonical_fact_removed")

        result.canonical_question = canonical
        result.primary_intent = patch.intent
        result.secondary_intents = []
        result.requested_information = list(patch.requested_information)
        result.normalized_semantics = {
            "canonical_query": canonical,
            "symptoms": list(merged_signals.symptoms),
            "components": list(merged_signals.components),
            "conditions": [*merged_signals.time_conditions, *merged_signals.operating_states],
            "requested_information": list(patch.requested_information),
        }
        patch_missing = [self.SLOT_TO_LEGACY[value] for value in patch.missing_slots]
        result.missing_information = self._unique([*assessment.missing_information, *patch_missing])
        result.ambiguity = patch.ambiguity in {"AMBIGUOUS", "INSUFFICIENT"}
        result.ambiguity_options = list(assessment.ambiguity_options) if result.ambiguity else []
        result.needs_clarification = bool(
            patch.needs_clarification
            or assessment.status in {"AMBIGUOUS", "INSUFFICIENT_INFORMATION"}
        )
        result.clarifying_question = patch.clarifying_question.strip() if result.needs_clarification else None
        result.confidence = patch.confidence
        result.retrieval_hypotheses = []
        result.retrieval_queries = []
        return result

    def merge_signals(
        self,
        signals: QuerySignals,
        *,
        conversation_state: dict[str, Any] | None,
    ) -> QuerySignals:
        output = signals.model_copy(deep=True)
        context_facts = deepcopy((conversation_state or {}).get("merged_confirmed_facts") or {})
        for key in self.CONTEXT_FACT_KEYS:
            current = list(getattr(output, key, []) or [])
            historical = list(context_facts.get(key) or [])
            setattr(output, key, self._unique([*historical, *current]))
        for key in self.CONTEXT_SCALAR_FACT_KEYS:
            current = getattr(output, key, None)
            historical = context_facts.get(key)
            if current is None and historical is not None:
                setattr(output, key, historical)
        return output

    @staticmethod
    def _apply_explicit_facts(result: QueryUnderstandingResult, signals: QuerySignals) -> None:
        result.device_models = list(signals.device_models)
        result.product_families = QueryUnderstandingMergeService._unique([
            signals.product_family, *QueryUnderstandingMergeService._families(signals.device_models),
        ])
        result.equipment_categories = QueryUnderstandingMergeService._equipment_categories(signals.device_models)
        result.components = list(signals.components)
        result.symptoms = list(signals.symptoms)
        result.conditions = [*signals.time_conditions, *signals.operating_states]
        result.alarm_codes = list(signals.alarm_codes)
        result.alarm_names = list(signals.alarm_names)
        result.confirmed_facts = {
            "manufacturer": signals.manufacturer,
            "product_family": signals.product_family,
            "model": signals.model,
            "model_original": signals.model_original,
            "alarm_code": signals.alarm_code,
            "fault_type": signals.fault_type,
            "maintenance_intent": signals.maintenance_intent,
            "safety_risk": signals.safety_risk,
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
    def _adds_explicit_entity(candidate: QuerySignals, confirmed: QuerySignals) -> bool:
        return bool(
            set(candidate.device_models) - set(confirmed.device_models)
            or set(candidate.alarm_codes) - set(confirmed.alarm_codes)
            or set(candidate.alarm_names) - set(confirmed.alarm_names)
        )

    @staticmethod
    def _families(models: list[str]) -> list[str]:
        values = []
        for model in models:
            lowered = model.lower()
            if lowered.startswith("sun2000"):
                values.append("SUN2000")
            elif lowered.startswith("luna2000"):
                values.append("LUNA2000")
            elif lowered.startswith("smartlogger"):
                values.append("SmartLogger")
        return QueryUnderstandingMergeService._unique(values)

    @staticmethod
    def _equipment_categories(models: list[str]) -> list[str]:
        values = []
        for model in models:
            lowered = model.lower()
            if lowered.startswith("sun2000"):
                values.append("pv_inverter")
            elif lowered.startswith("luna2000"):
                values.append("energy_storage")
            elif lowered.startswith("smartlogger"):
                values.append("communication_management_device")
        return QueryUnderstandingMergeService._unique(values)

    @staticmethod
    def _unique(values: list[Any]) -> list[str]:
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
