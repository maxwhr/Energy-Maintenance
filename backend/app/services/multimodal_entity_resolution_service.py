from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from app.models import MultimodalEvidenceItem, MultimodalMaintenanceCase
from app.services.query_understanding_service import normalize_alarm_identifier, normalize_device_model


@dataclass(slots=True)
class ResolutionCandidate:
    value: str
    entity_type: str
    priority: int
    confidence: float
    source: str
    evidence_id: str | None = None
    confirmed: bool = False


@dataclass(slots=True)
class MultimodalEntityResolution:
    resolved_device_model: str | None = None
    resolved_product_family: str | None = None
    resolved_equipment_category: str | None = None
    resolved_alarm_codes: list[str] = field(default_factory=list)
    resolved_components: list[str] = field(default_factory=list)
    resolved_conditions: list[str] = field(default_factory=list)
    resolution_confidence: float = 0.0
    resolution_sources: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultimodalEntityResolutionService:
    """Resolve only evidence-backed entities with an explicit priority ladder."""

    def resolve(
        self,
        case: MultimodalMaintenanceCase,
        evidence_items: Iterable[MultimodalEvidenceItem],
        *,
        bound_device: Any | None = None,
    ) -> MultimodalEntityResolution:
        models: list[ResolutionCandidate] = []
        alarms: list[ResolutionCandidate] = []
        components: list[ResolutionCandidate] = []
        equipment: list[ResolutionCandidate] = []

        if bound_device is not None:
            if getattr(bound_device, "model", None):
                models.append(self._candidate(bound_device.model, "device_model", 2, 1.0, "BOUND_DEVICE"))
            if getattr(bound_device, "device_type", None):
                equipment.append(self._candidate(bound_device.device_type, "equipment_category", 2, 1.0, "BOUND_DEVICE"))

        confirmed_facts = case.user_confirmed_facts or {}
        for fact in confirmed_facts.values():
            if not isinstance(fact, dict):
                continue
            value = str(fact.get("value") or "").strip()
            kind = str(fact.get("evidence_type") or "")
            if value and kind == "DEVICE_MODEL":
                models.append(self._candidate(value, "device_model", 1, 1.0, "USER_CONFIRMED"))
            elif value and kind == "ALARM_CODE":
                alarms.append(self._candidate(value, "alarm_code", 1, 1.0, "USER_CONFIRMED"))

        for item in evidence_items:
            if item.observation_status in {"REJECTED", "CONTRADICTED"} or item.contradicted:
                continue
            confirmed = bool(item.user_confirmed or item.observation_status == "USER_CONFIRMED")
            if confirmed:
                priority = 1
                source = "USER_CONFIRMED"
            elif item.source_type == "OCR_PROVIDER" and item.evidence_type in {"DEVICE_MODEL", "NAMEPLATE"}:
                priority, source = 3, "NAMEPLATE_OCR"
            elif item.source_type == "OCR_PROVIDER" and item.evidence_type in {"ALARM_CODE", "SCREEN_TEXT"}:
                priority, source = 4, "SCREEN_OCR"
            elif item.source_type == "MULTIMODAL_PROVIDER":
                priority, source = 5, "VISUAL_INFERENCE"
            else:
                priority, source = 6, item.source_type
            for value in item.device_model_candidates or []:
                models.append(self._candidate(value, "device_model", priority, item.confidence, source, item.evidence_id, confirmed))
            for value in item.alarm_code_candidates or []:
                alarms.append(self._candidate(value, "alarm_code", priority, item.confidence, source, item.evidence_id, confirmed))
            for value in item.component_candidates or []:
                components.append(self._candidate(value, "component", priority, item.confidence, source, item.evidence_id, confirmed))
            visual_type = (item.metadata_json or {}).get("candidate_device_type")
            if visual_type:
                equipment.append(self._candidate(visual_type, "equipment_category", priority, item.confidence, source, item.evidence_id, confirmed))

        if case.device_model:
            models.append(self._candidate(case.device_model, "device_model", 6, 0.6, "CASE_HINT"))
        if case.equipment_category:
            equipment.append(self._candidate(case.equipment_category, "equipment_category", 6, 0.6, "CASE_HINT"))

        resolved_model, model_sources, model_conflicts = self._resolve_single(models, normalize_device_model)
        resolved_equipment, equipment_sources, equipment_conflicts = self._resolve_single(equipment, lambda value: value.lower())
        resolved_alarms, alarm_sources, alarm_conflicts = self._resolve_many(alarms, normalize_alarm_identifier)
        resolved_components, component_sources, _ = self._resolve_many(components, lambda value: value.lower())
        sources = [*model_sources, *equipment_sources, *alarm_sources, *component_sources]
        conflicts = [*model_conflicts, *equipment_conflicts, *alarm_conflicts]
        confidence_values = [source["confidence"] for source in sources if source.get("selected")]
        missing = []
        if not resolved_model:
            missing.append("device_model")
        if not resolved_alarms and not case.reported_symptoms:
            missing.append("alarm_code_or_symptom")
        if conflicts:
            missing.append("conflict_resolution")
        return MultimodalEntityResolution(
            resolved_device_model=resolved_model,
            resolved_product_family=self._product_family(resolved_model),
            resolved_equipment_category=resolved_equipment,
            resolved_alarm_codes=resolved_alarms,
            resolved_components=resolved_components,
            resolved_conditions=list(dict.fromkeys(case.occurrence_conditions or [])),
            resolution_confidence=round(min(confidence_values), 4) if confidence_values else 0.0,
            resolution_sources=sources,
            conflicts=conflicts,
            missing_information=list(dict.fromkeys(missing)),
        )

    @staticmethod
    def _candidate(value, entity_type, priority, confidence, source, evidence_id=None, confirmed=False):
        try:
            score = max(0.0, min(float(confidence), 1.0))
        except (TypeError, ValueError):
            score = 0.0
        return ResolutionCandidate(str(value).strip(), entity_type, priority, score, source, evidence_id, confirmed)

    @staticmethod
    def _resolve_single(candidates, normalizer):
        usable = [item for item in candidates if item.value and (item.confirmed or item.confidence >= 0.60)]
        if not usable:
            return None, [], []
        grouped: dict[str, list[ResolutionCandidate]] = {}
        for item in usable:
            grouped.setdefault(normalizer(item.value), []).append(item)
        ranked = sorted(grouped.items(), key=lambda pair: (min(item.priority for item in pair[1]), -max(item.confidence for item in pair[1]), pair[0]))
        selected_value, selected_items = ranked[0]
        selected_priority = min(item.priority for item in selected_items)
        sources = MultimodalEntityResolutionService._source_payload(grouped, selected_value)
        conflicts = []
        for value, items in ranked[1:]:
            if min(item.priority for item in items) <= max(4, selected_priority + 1):
                conflicts.append({
                    "entity_type": selected_items[0].entity_type,
                    "selected_value": selected_value,
                    "conflicting_value": value,
                    "selected_evidence_ids": [item.evidence_id for item in selected_items if item.evidence_id],
                    "conflicting_evidence_ids": [item.evidence_id for item in items if item.evidence_id],
                })
        return selected_value, sources, conflicts

    @staticmethod
    def _resolve_many(candidates, normalizer):
        usable = [item for item in candidates if item.value and (item.confirmed or item.confidence >= 0.60)]
        if not usable:
            return [], [], []
        grouped: dict[str, list[ResolutionCandidate]] = {}
        for item in usable:
            grouped.setdefault(normalizer(item.value), []).append(item)
        best_priority = min(item.priority for item in usable)
        confirmed_values = {value for value, items in grouped.items() if any(item.confirmed for item in items)}
        selected = sorted(confirmed_values) if confirmed_values else sorted(
            value for value, items in grouped.items() if min(item.priority for item in items) <= min(4, best_priority + 1)
        )
        sources = MultimodalEntityResolutionService._source_payload(grouped, set(selected))
        conflicts = []
        if confirmed_values:
            for value, items in grouped.items():
                if value not in confirmed_values and min(item.priority for item in items) <= 4:
                    conflicts.append({
                        "entity_type": usable[0].entity_type,
                        "selected_value": sorted(confirmed_values),
                        "conflicting_value": value,
                        "conflicting_evidence_ids": [item.evidence_id for item in items if item.evidence_id],
                    })
        return selected, sources, conflicts

    @staticmethod
    def _source_payload(grouped, selected):
        selected_set = {selected} if isinstance(selected, str) else set(selected)
        result = []
        for value, items in grouped.items():
            for item in items:
                result.append({
                    "entity_type": item.entity_type,
                    "value": value,
                    "priority": item.priority,
                    "confidence": item.confidence,
                    "source": item.source,
                    "evidence_id": item.evidence_id,
                    "confirmed": item.confirmed,
                    "selected": value in selected_set,
                })
        return result

    @staticmethod
    def _product_family(model: str | None) -> str | None:
        upper = (model or "").upper()
        if upper.startswith("SUN2000"):
            return "SUN2000"
        if upper.startswith("LUNA2000"):
            return "LUNA2000"
        if upper.startswith("SMARTLOGGER"):
            return "SmartLogger"
        if upper.startswith("SG"):
            return "SG"
        return None
