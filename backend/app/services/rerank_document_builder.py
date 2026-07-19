from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from app.schemas.query_understanding import QueryUnderstandingResult
from app.services.rrf_fusion_service import QueryAwareCandidate


@dataclass(frozen=True, slots=True)
class RerankDocument:
    candidate_id: str
    text: str
    text_hash: str
    text_length: int


class RerankDocumentBuilder:
    MAX_CHARS = 1500
    TARGET_MIN_CHARS = 800

    def build(
        self,
        candidate: QueryAwareCandidate,
        *,
        understanding: QueryUnderstandingResult | None = None,
    ) -> RerankDocument:
        metadata = self._metadata(candidate)
        semantic = metadata.get("semantic_unit") if isinstance(metadata.get("semantic_unit"), dict) else {}
        requested = list(understanding.requested_information) if understanding else []
        fields: list[tuple[str, Any]] = [
            ("请求信息", requested),
            ("文档类型", metadata.get("document_type") or getattr(candidate.document, "document_type", None)),
            ("产品族", metadata.get("product_family") or getattr(candidate.document, "product_series", None)),
            ("设备型号", self._values(metadata, semantic, "device_models", "device_model", "applicable_device_models")),
            ("告警", [
                *self._values(metadata, semantic, "alarm_codes", "alarm_code"),
                *self._values(metadata, semantic, "alarm_names", "alarm_name"),
            ]),
            ("章节", candidate.section_title or semantic.get("title")),
            ("单元类型", semantic.get("semantic_unit_type") or semantic.get("unit_type") or candidate.evidence_level),
            ("症状", self._values(metadata, semantic, "symptoms")),
            ("原因", self._values(metadata, semantic, "causes")),
            ("动作", self._values(metadata, semantic, "actions")),
            ("步骤", self._values(metadata, semantic, "procedure_steps")),
            ("前提", self._values(metadata, semantic, "prerequisites")),
            ("验证", self._values(metadata, semantic, "verification_steps")),
            ("安全要求", self._values(metadata, semantic, "safety_requirements")),
            ("通信", self._values(metadata, semantic, "communication_terms")),
        ]
        lines = [self._line(label, value) for label, value in fields]
        lines = [line for line in lines if line]
        source = " ".join((candidate.content or "").split())
        evidence = " ".join(str(semantic.get("canonical_evidence") or "").split())
        if evidence and evidence not in source:
            lines.insert(7, f"直接证据：{evidence}")
        lines.append(f"来源摘录：{source}")
        text = "\n".join(lines)
        if len(text) > self.MAX_CHARS:
            prefix = "\n".join(lines[:-1])
            available = max(0, self.MAX_CHARS - len(prefix) - len("\n来源摘录："))
            text = f"{prefix}\n来源摘录：{source[:available]}" if prefix else source[: self.MAX_CHARS]
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return RerankDocument(candidate.candidate_id, text, digest, len(text))

    @staticmethod
    def _metadata(candidate: QueryAwareCandidate) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for source in (
            getattr(candidate.document, "metadata_json", None),
            getattr(candidate.chunk, "metadata_json", None),
        ):
            if isinstance(source, dict):
                output.update(source)
        return output

    @staticmethod
    def _values(metadata: dict[str, Any], semantic: dict[str, Any], *keys: str) -> list[str]:
        values: list[str] = []
        for source in (metadata, semantic):
            for key in keys:
                value = source.get(key)
                items = value if isinstance(value, list) else [value] if value else []
                values.extend(str(item).strip() for item in items if str(item).strip())
        return list(dict.fromkeys(values))

    @staticmethod
    def _line(label: str, value: Any) -> str:
        items = value if isinstance(value, list) else [value] if value else []
        text = "；".join(str(item).strip() for item in items if str(item).strip())
        return f"{label}：{text}" if text else ""
