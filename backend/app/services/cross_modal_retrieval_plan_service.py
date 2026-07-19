from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from app.models import MultimodalEvidenceItem
from app.schemas.retrieval_scope import HUAWEI_SUN2000_COMPETITION_SCOPE_ID
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution


@dataclass(slots=True)
class CrossModalQuery:
    query_type: str
    query: str
    evidence_ids: list[str] = field(default_factory=list)
    hypothesis_signals: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CrossModalRetrievalPlan:
    original_query: str
    queries: list[CrossModalQuery]
    scope_id: str
    resolved_device_model: str | None = None
    resolved_product_family: str | None = None
    resolved_alarm_codes: list[str] = field(default_factory=list)
    dedicated_rerank_status: str = "DEFERRED_QWEN3_RERANK_CONFIG"
    deterministic_fallback: bool = True

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CrossModalRetrievalPlanService:
    def build(
        self,
        *,
        original_query: str,
        normalized_query: str | None,
        confirmed_facts: dict[str, Any],
        resolution: MultimodalEntityResolution,
        evidence_items: Iterable[MultimodalEvidenceItem],
        occurrence_conditions: list[str],
        requested_information: list[str] | None = None,
        scope_id: str = HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
    ) -> CrossModalRetrievalPlan:
        original = " ".join((original_query or normalized_query or "").split()).strip()
        if not original:
            raise ValueError("original query is required")
        queries = [CrossModalQuery("ORIGINAL_TEXT", original)]
        items = [item for item in evidence_items if item.observation_status not in {"REJECTED", "CONTRADICTED"}]
        model = resolution.resolved_device_model
        conditions = list(dict.fromkeys(occurrence_conditions or resolution.resolved_conditions))

        entity_parts = [part for part in [model, *resolution.resolved_alarm_codes, *conditions] if part]
        if entity_parts:
            queries.append(CrossModalQuery(
                "OCR_ENTITY_QUERY",
                " ".join(entity_parts),
                self._evidence_ids(items, {"DEVICE_MODEL", "ALARM_CODE", "NAMEPLATE", "SCREEN_TEXT"}),
            ))

        visual_signals: list[str] = []
        visual_ids: list[str] = []
        hypotheses: list[str] = []
        for item in items:
            if item.modality != "VISUAL_REGION":
                continue
            values = [*item.indicator_state_candidates, *item.component_candidates, *item.symptom_candidates]
            if item.normalized_text:
                values.append(item.normalized_text)
            for value in values:
                cleaned = " ".join(str(value).split()).strip()
                if cleaned and cleaned not in visual_signals:
                    visual_signals.append(cleaned)
                    visual_ids.append(item.evidence_id)
                    if item.observation_status != "USER_CONFIRMED":
                        hypotheses.append(cleaned)
        if visual_signals:
            queries.append(CrossModalQuery(
                "VISUAL_SYMPTOM_QUERY",
                " ".join(part for part in [model, *visual_signals[:4], *conditions[:2]] if part),
                list(dict.fromkeys(visual_ids)),
                list(dict.fromkeys(hypotheses)),
            ))
        if resolution.resolved_alarm_codes:
            queries.append(CrossModalQuery(
                "ALARM_QUERY",
                " ".join(part for part in [model, *resolution.resolved_alarm_codes, "告警原因 处理建议"] if part),
                self._evidence_ids(items, {"ALARM_CODE", "SCREEN_TEXT"}),
            ))
        requested = list(dict.fromkeys(requested_information or []))
        symptom_terms = list(dict.fromkeys([*resolution.resolved_components, *conditions, *requested]))
        if symptom_terms or visual_signals:
            queries.append(CrossModalQuery(
                "ACTION_OR_SAFETY_QUERY",
                " ".join(part for part in [model, *(symptom_terms or visual_signals[:3]), "排查 安全要求"] if part),
                self._evidence_ids(items, {"COMPONENT", "PHYSICAL_DAMAGE", "SAFETY_HAZARD", "INDICATOR_LIGHT"}),
            ))
        return CrossModalRetrievalPlan(
            original_query=original,
            queries=self._dedupe(queries)[:5],
            scope_id=scope_id,
            resolved_device_model=resolution.resolved_device_model,
            resolved_product_family=resolution.resolved_product_family,
            resolved_alarm_codes=list(resolution.resolved_alarm_codes),
        )

    @staticmethod
    def _evidence_ids(items, evidence_types):
        return [item.evidence_id for item in items if item.evidence_type in evidence_types]

    @staticmethod
    def _dedupe(items):
        result = []
        seen = set()
        for item in items:
            key = item.query.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
