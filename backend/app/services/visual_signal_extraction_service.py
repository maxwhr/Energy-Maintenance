from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.schemas.multimodal_case import MultimodalEvidenceCreate
from app.schemas.multimodal_signal import VisualRegion, VisualSignalResult


ALLOWED_COMPONENTS = {
    "fan", "风扇", "heat_sink", "散热器", "cable", "线缆", "switch", "开关", "connector", "接口",
    "display", "屏幕", "indicator", "指示灯", "nameplate", "铭牌", "fuse", "熔丝",
}
ALLOWED_COLORS = {"red", "green", "yellow", "blue", "white", "off", "红", "绿", "黄", "蓝", "白", "熄灭"}
ALLOWED_INDICATOR_MODES = {"steady", "blinking", "off", "unknown", "常亮", "闪烁", "熄灭", "未知"}
UNSAFE_PROVIDER_FIELDS = {
    "diagnosis", "diagnostic_conclusion", "possible_faults", "possible_fault_clues", "recommended_actions",
    "recommended_next_steps", "repair_steps", "hidden_reasoning", "chain_of_thought", "alarm_codes", "device_model",
}


class VisualSignalExtractionService:
    """Constrain provider output to visible, region-addressable observations."""

    def __init__(self):
        self.settings = get_settings()

    def normalize(self, payload: dict[str, Any]) -> VisualSignalResult:
        source = payload.get("normalized_result") if isinstance(payload.get("normalized_result"), dict) else payload
        removed = sorted(key for key in UNSAFE_PROVIDER_FIELDS if key in source and source.get(key) not in (None, [], {}, ""))
        observations = self._strings(source.get("observations") or source.get("visual_findings"))
        raw_regions = source.get("regions") if isinstance(source.get("regions"), list) else []
        regions: list[VisualRegion] = []
        for index, raw in enumerate(raw_regions):
            if not isinstance(raw, dict):
                continue
            bbox = self._bbox(raw.get("bounding_box") or raw.get("bbox"))
            region_type = self._region_type(raw.get("region_type") or raw.get("type"))
            attributes = self._visible_attributes(raw.get("attributes") if isinstance(raw.get("attributes"), dict) else raw)
            regions.append(VisualRegion(
                region_id=str(raw.get("region_id") or f"visual_region_{index}"),
                bounding_box=bbox,
                region_type=region_type,
                text=str(raw.get("text") or raw.get("observation") or "").strip()[:1000] or None,
                attributes=attributes,
                confidence=self._confidence(raw.get("confidence"), default=source.get("confidence")),
            ))
        if observations and not regions:
            for index, observation in enumerate(observations):
                regions.append(VisualRegion(
                    region_id=f"visual_full_{index}",
                    bounding_box=[0.0, 0.0, 1.0, 1.0],
                    region_type="GENERAL",
                    text=observation,
                    confidence=self._confidence(source.get("confidence")),
                ))
        components = [item for item in self._strings(source.get("candidate_components")) if item.lower() in {part.lower() for part in ALLOWED_COMPONENTS}]
        indicator_states = self._indicator_states(source.get("indicator_states"))
        return VisualSignalResult(
            observations=observations,
            regions=regions,
            candidate_device_type=self._candidate_device_type(source.get("candidate_device_type")),
            candidate_components=list(dict.fromkeys(components)),
            indicator_states=indicator_states,
            visible_damage=self._strings(source.get("visible_damage")),
            screen_present=bool(source.get("screen_present")),
            nameplate_present=bool(source.get("nameplate_present")),
            needs_ocr=bool(source.get("needs_ocr")),
            image_quality_issue=self._strings(source.get("image_quality_issue")),
            confidence=self._confidence(source.get("confidence")),
            provider=self._short(source.get("provider") or payload.get("provider"), 64),
            provider_model=self._short(source.get("provider_model") or source.get("model") or payload.get("model"), 128),
            provider_trace_id=self._short(source.get("provider_trace_id") or source.get("external_trace_id"), 128),
            unsupported_fields_removed=removed,
        )

    def to_evidence(
        self,
        payload: dict[str, Any],
        *,
        media_id: UUID,
        analysis_id: UUID | None,
    ) -> list[MultimodalEvidenceCreate]:
        result = self.normalize(payload)
        evidence: list[MultimodalEvidenceCreate] = []
        for index, region in enumerate(result.regions):
            confidence = min(region.confidence, result.confidence or region.confidence)
            status = "INFERRED" if confidence >= self.settings.MULTIMODAL_VISION_MIN_CONFIDENCE else "LOW_CONFIDENCE"
            evidence_type = self._evidence_type(region)
            source_hash = hashlib.sha256(json.dumps({
                "media_id": str(media_id), "region_id": region.region_id, "bbox": region.bounding_box,
                "text": region.text, "attributes": region.attributes,
            }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            indicator = self._indicator_candidates(region.attributes, result.indicator_states)
            evidence.append(MultimodalEvidenceCreate(
                media_id=media_id,
                analysis_id=analysis_id,
                region_id=region.region_id,
                modality="VISUAL_REGION",
                evidence_type=evidence_type,
                source_type="MULTIMODAL_PROVIDER",
                source_hash=source_hash,
                observed_text=region.text,
                normalized_text=region.text,
                visual_attributes=region.attributes,
                bounding_box=region.bounding_box,
                page_or_frame_locator={
                    "media_id": str(media_id),
                    "region_index": index,
                    "region_type": region.region_type,
                    "locator_type": "visual_region" if region.bounding_box != [0.0, 0.0, 1.0, 1.0] else "full_image_fallback",
                },
                component_candidates=result.candidate_components if evidence_type == "COMPONENT" else [],
                indicator_state_candidates=indicator,
                symptom_candidates=result.visible_damage if evidence_type in {"PHYSICAL_DAMAGE", "SAFETY_HAZARD"} else [],
                confidence=confidence,
                observation_status=status,
                provider=result.provider,
                provider_model=result.provider_model,
                provider_trace_id=result.provider_trace_id,
                metadata_json={
                    "cropped_image_hash": region.attributes.get("cropped_image_hash"),
                    "candidate_device_type": result.candidate_device_type,
                    "screen_present": result.screen_present,
                    "nameplate_present": result.nameplate_present,
                    "needs_ocr": result.needs_ocr,
                    "image_quality_issue": result.image_quality_issue,
                    "unsupported_fields_removed": result.unsupported_fields_removed,
                    "device_model_candidates_suppressed": True,
                    "alarm_code_candidates_suppressed": True,
                },
            ))
        return evidence

    @staticmethod
    def _visible_attributes(value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"color", "state", "component", "damage", "cropped_image_hash", "screen", "nameplate", "connection"}
        return {key: value[key] for key in allowed if key in value and isinstance(value[key], (str, int, float, bool, type(None)))}

    @staticmethod
    def _indicator_states(value: Any) -> list[dict[str, Any]]:
        items = value if isinstance(value, list) else []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            color = str(item.get("color") or "unknown").strip().lower()
            state = str(item.get("state") or item.get("mode") or "unknown").strip().lower()
            if color not in {part.lower() for part in ALLOWED_COLORS}:
                color = "unknown"
            if state not in {part.lower() for part in ALLOWED_INDICATOR_MODES}:
                state = "unknown"
            result.append({"color": color, "state": state, "confidence": VisualSignalExtractionService._confidence(item.get("confidence"))})
        return result

    @staticmethod
    def _indicator_candidates(attributes: dict[str, Any], aggregate: list[dict[str, Any]]) -> list[str]:
        values = []
        color = str(attributes.get("color") or "").strip()
        state = str(attributes.get("state") or "").strip()
        if color or state:
            values.append(" ".join(part for part in (color, state) if part))
        values.extend(" ".join(part for part in (str(item.get("color") or ""), str(item.get("state") or "")) if part) for item in aggregate)
        return list(dict.fromkeys(value for value in values if value))

    @staticmethod
    def _evidence_type(region: VisualRegion) -> str:
        return {
            "NAMEPLATE": "NAMEPLATE", "SCREEN": "SCREEN_TEXT", "INDICATOR_LIGHT": "INDICATOR_LIGHT",
            "COMPONENT": "COMPONENT", "PHYSICAL_DAMAGE": "PHYSICAL_DAMAGE", "GENERAL": "GENERAL_OBSERVATION",
        }[region.region_type]

    @staticmethod
    def _region_type(value: Any) -> str:
        normalized = str(value or "GENERAL").strip().upper()
        aliases = {"INDICATOR": "INDICATOR_LIGHT", "LIGHT": "INDICATOR_LIGHT", "DAMAGE": "PHYSICAL_DAMAGE"}
        normalized = aliases.get(normalized, normalized)
        return normalized if normalized in {"NAMEPLATE", "SCREEN", "INDICATOR_LIGHT", "COMPONENT", "PHYSICAL_DAMAGE", "GENERAL"} else "GENERAL"

    @staticmethod
    def _bbox(value: Any) -> list[float]:
        if isinstance(value, dict):
            raw = [value.get("x1", value.get("left", 0)), value.get("y1", value.get("top", 0)), value.get("x2", value.get("right", 1)), value.get("y2", value.get("bottom", 1))]
        elif isinstance(value, (list, tuple)) and len(value) >= 4:
            raw = value[:4]
        else:
            return [0.0, 0.0, 1.0, 1.0]
        try:
            box = [max(0.0, min(float(item), 1.0)) for item in raw]
        except (TypeError, ValueError):
            return [0.0, 0.0, 1.0, 1.0]
        if box[2] <= box[0] or box[3] <= box[1]:
            return [0.0, 0.0, 1.0, 1.0]
        return [round(item, 6) for item in box]

    @staticmethod
    def _strings(value: Any) -> list[str]:
        items = value if isinstance(value, list) else ([] if value in (None, "") else [value])
        result = []
        for item in items:
            if isinstance(item, dict):
                item = item.get("observation") or item.get("finding") or item.get("value") or ""
            cleaned = " ".join(str(item).split()).strip()[:1000]
            if cleaned:
                result.append(cleaned)
        return list(dict.fromkeys(result))

    @staticmethod
    def _candidate_device_type(value: Any) -> str | None:
        normalized = str(value or "").strip().lower()
        allowed = {"pv_inverter", "battery_system", "smart_logger", "monitoring_platform", "unknown"}
        return normalized if normalized in allowed else None

    @staticmethod
    def _confidence(value: Any, *, default: Any = 0.0) -> float:
        try:
            parsed = float(value if value is not None else default)
        except (TypeError, ValueError):
            parsed = 0.0
        if parsed > 1 and parsed <= 100:
            parsed /= 100
        return round(max(0.0, min(parsed, 0.99)), 4)

    @staticmethod
    def _short(value: Any, length: int) -> str | None:
        cleaned = str(value or "").strip()
        return cleaned[:length] or None
