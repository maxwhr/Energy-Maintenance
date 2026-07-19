from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.schemas.multimodal_case import MultimodalEvidenceCreate
from app.services.query_understanding_service import normalize_alarm_identifier, normalize_device_model


MODEL_PATTERN = re.compile(
    r"\b(?:SUN2000(?:[-(][A-Z0-9/()\-]+)?|LUNA2000(?:[-(][A-Z0-9/()\-]+)?|SMARTLOGGER\d*|SG\d+[A-Z0-9\-]*)\b",
    re.IGNORECASE,
)
ALARM_CONTEXT_PATTERN = re.compile(
    r"(?:告警(?:代码|码)?|故障(?:代码|码)?|ALARM(?:\s+CODE)?|FAULT(?:\s+CODE)?)\s*[:：#]?\s*([A-Z]{0,5}[-_]?\d{3,6})\b",
    re.IGNORECASE,
)
PREFIXED_ALARM_PATTERN = re.compile(r"\b(?:ALM|FAULT|ERR)[-_]?\d{3,6}\b", re.IGNORECASE)
SERIAL_PATTERN = re.compile(r"(?:SN|S/N|序列号)\s*[:：#]?\s*([A-Z0-9\-]{8,32})\b", re.IGNORECASE)
PARAMETER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:V|A|W|KW|KWH|HZ|℃|°C)\b", re.IGNORECASE)
DATE_TIME_PATTERN = re.compile(r"\b(?:20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}:\d{2}(?::\d{2})?)\b")
COMPONENT_TERMS = ("风扇", "MPPT", "组串", "直流侧", "交流侧", "通信模块", "散热器", "接地", "熔丝", "开关", "线缆")
COMMUNICATION_TERMS = ("WIFI", "WLAN", "RS485", "4G", "以太网", "ETHERNET")
STATE_TERMS = ("启动", "停止", "故障", "告警", "正常", "离线", "并网", "待机")


@dataclass(slots=True)
class NormalizedOCRBlock:
    raw_block_hash: str
    raw_text: str
    normalized_text: str
    bounding_box: list[float]
    confidence: float
    line_order: int
    region_group: str
    provider_trace_id: str | None
    device_models: list[str]
    product_families: list[str]
    alarm_codes: list[str]
    serial_number_candidates: list[str]
    parameters: list[str]
    communication_terms: list[str]
    state_terms: list[str]


class OcrEvidenceNormalizationService:
    """Normalize OCR blocks into traceable observations without confirming them."""

    def __init__(self):
        self.settings = get_settings()

    def normalize_blocks(
        self,
        payload: dict[str, Any],
        *,
        media_id: UUID,
        provider_trace_id: str | None = None,
    ) -> list[NormalizedOCRBlock]:
        regions = payload.get("regions")
        blocks = regions if isinstance(regions, list) and regions else [{"text": payload.get("text") or ""}]
        normalized: list[NormalizedOCRBlock] = []
        width = self._positive_number(payload.get("width") or payload.get("image_width"))
        height = self._positive_number(payload.get("height") or payload.get("image_height"))
        default_confidence = self._confidence(payload.get("confidence"))
        for index, block in enumerate(blocks):
            if not isinstance(block, dict):
                block = {"text": str(block)}
            raw_text = str(block.get("text") or block.get("recognized_text") or "").strip()
            if not raw_text:
                continue
            text = self._normalize_text(raw_text)
            confidence = self._confidence(block.get("confidence"), default=default_confidence)
            bbox = self._bbox(block.get("bounding_box") or block.get("bbox"), width=width, height=height)
            models = self._unique(normalize_device_model(item) for item in MODEL_PATTERN.findall(text))
            alarms = self._alarm_codes(text, models)
            serials = self._unique(SERIAL_PATTERN.findall(text))
            parameters = self._unique(PARAMETER_PATTERN.findall(text))
            block_hash = self._hash({
                "media_id": str(media_id),
                "line_order": index,
                "raw_text": raw_text,
                "bbox": bbox,
            })
            normalized.append(NormalizedOCRBlock(
                raw_block_hash=block_hash,
                raw_text=raw_text,
                normalized_text=text,
                bounding_box=bbox,
                confidence=confidence,
                line_order=index,
                region_group=str(block.get("region_group") or f"ocr_group_{index}"),
                provider_trace_id=provider_trace_id or payload.get("provider_trace_id") or payload.get("external_trace_id"),
                device_models=models,
                product_families=self._unique(self._product_family(model) for model in models),
                alarm_codes=alarms,
                serial_number_candidates=serials,
                parameters=parameters,
                communication_terms=self._matches(text, COMMUNICATION_TERMS),
                state_terms=self._matches(text, STATE_TERMS),
            ))
        return normalized

    def to_evidence(
        self,
        payload: dict[str, Any],
        *,
        media_id: UUID,
        ocr_result_id: UUID | None,
        provider: str,
        provider_model: str | None,
        provider_trace_id: str | None,
    ) -> list[MultimodalEvidenceCreate]:
        evidence: list[MultimodalEvidenceCreate] = []
        for block in self.normalize_blocks(payload, media_id=media_id, provider_trace_id=provider_trace_id):
            status = "OBSERVED" if block.confidence >= self.settings.MULTIMODAL_OCR_MIN_CONFIDENCE else "LOW_CONFIDENCE"
            common = {
                "media_id": media_id,
                "ocr_result_id": ocr_result_id,
                "region_id": f"ocr_{block.raw_block_hash[:20]}",
                "modality": "OCR_TEXT",
                "source_type": "OCR_PROVIDER",
                "source_hash": block.raw_block_hash,
                "observed_text": block.raw_text,
                "normalized_text": block.normalized_text,
                "bounding_box": block.bounding_box,
                "page_or_frame_locator": {
                    "media_id": str(media_id),
                    "line_order": block.line_order,
                    "region_group": block.region_group,
                    "locator_type": "ocr_region" if block.bounding_box != [0.0, 0.0, 1.0, 1.0] else "full_image_fallback",
                },
                "confidence": block.confidence,
                "observation_status": status,
                "provider": provider,
                "provider_model": provider_model,
                "provider_trace_id": block.provider_trace_id,
                "metadata_json": {
                    "raw_block_hash": block.raw_block_hash,
                    "line_order": block.line_order,
                    "region_group": block.region_group,
                    "product_families": block.product_families,
                    "serial_number_candidates": block.serial_number_candidates,
                    "parameters": block.parameters,
                    "communication_terms": block.communication_terms,
                    "state_terms": block.state_terms,
                    "raw_and_normalized_preserved": True,
                },
            }
            evidence.append(MultimodalEvidenceCreate(
                **common,
                evidence_type=self._evidence_type(block),
                device_model_candidates=block.device_models,
                alarm_code_candidates=block.alarm_codes,
                component_candidates=self._matches(block.normalized_text, COMPONENT_TERMS),
                symptom_candidates=self._unique([*block.communication_terms, *block.state_terms]),
            ))
        return evidence

    @staticmethod
    def _evidence_type(block: NormalizedOCRBlock) -> str:
        if block.device_models:
            return "DEVICE_MODEL"
        if block.alarm_codes:
            return "ALARM_CODE"
        if block.serial_number_candidates:
            return "NAMEPLATE"
        return "SCREEN_TEXT"

    @staticmethod
    def _alarm_codes(text: str, device_models: list[str]) -> list[str]:
        values = [*ALARM_CONTEXT_PATTERN.findall(text), *PREFIXED_ALARM_PATTERN.findall(text)]
        normalized_models = set(device_models)
        alarms = []
        for value in values:
            normalized = normalize_alarm_identifier(value)
            if normalized in normalized_models or DATE_TIME_PATTERN.fullmatch(value.strip()) or PARAMETER_PATTERN.fullmatch(value.strip()):
                continue
            alarms.append(normalized)
        return OcrEvidenceNormalizationService._unique(alarms)

    @staticmethod
    def _product_family(model: str) -> str:
        upper = model.upper()
        for family in ("SUN2000", "LUNA2000", "SMARTLOGGER", "SG"):
            if upper.startswith(family):
                return "SmartLogger" if family == "SMARTLOGGER" else family
        return ""

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).replace("\x00", " ")
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _bbox(value: Any, *, width: float | None, height: float | None) -> list[float]:
        if isinstance(value, dict):
            raw = [value.get("x1", value.get("left", value.get("x", 0))), value.get("y1", value.get("top", value.get("y", 0))), value.get("x2", value.get("right", 1)), value.get("y2", value.get("bottom", 1))]
            if "width" in value and "x2" not in value and "right" not in value:
                raw[2] = float(raw[0] or 0) + float(value.get("width") or 0)
            if "height" in value and "y2" not in value and "bottom" not in value:
                raw[3] = float(raw[1] or 0) + float(value.get("height") or 0)
        elif isinstance(value, (list, tuple)) and len(value) >= 4:
            raw = list(value[:4])
        else:
            return [0.0, 0.0, 1.0, 1.0]
        try:
            box = [float(item) for item in raw]
        except (TypeError, ValueError):
            return [0.0, 0.0, 1.0, 1.0]
        if max(box) > 1.0 and width and height:
            box = [box[0] / width, box[1] / height, box[2] / width, box[3] / height]
        return [round(max(0.0, min(item, 1.0)), 6) for item in box]

    @staticmethod
    def _confidence(value: Any, *, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = default
        if parsed > 1.0 and parsed <= 100.0:
            parsed /= 100.0
        return round(max(0.0, min(parsed, 0.99)), 4)

    @staticmethod
    def _positive_number(value: Any) -> float | None:
        try:
            parsed = float(value)
            return parsed if parsed > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _matches(text: str, terms: tuple[str, ...]) -> list[str]:
        upper = text.upper()
        return [term for term in terms if term.upper() in upper]

    @staticmethod
    def _unique(values) -> list[str]:
        return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))

    @staticmethod
    def _hash(value: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    @staticmethod
    def block_payload(block: NormalizedOCRBlock) -> dict[str, Any]:
        return asdict(block)
