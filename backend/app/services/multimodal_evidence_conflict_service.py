from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from app.models import MultimodalEvidenceItem
from app.services.query_understanding_service import normalize_alarm_identifier, normalize_device_model


@dataclass(slots=True)
class EvidenceConflictCandidate:
    conflict_id: str
    conflict_type: str
    evidence_ids: list[str]
    severity: str
    resolution_required: bool
    recommended_question: str
    resolution_status: str = "OPEN"

    def as_dict(self) -> dict:
        return asdict(self)


class MultimodalEvidenceConflictService:
    def detect(self, evidence_items: Iterable[MultimodalEvidenceItem]) -> list[EvidenceConflictCandidate]:
        items = [item for item in evidence_items if item.observation_status not in {"REJECTED", "CONTRADICTED"}]
        conflicts = []
        conflicts.extend(self._entity_conflicts(items, "device_model_candidates", "DEVICE_MODEL_CONFLICT", normalize_device_model))
        conflicts.extend(self._entity_conflicts(items, "alarm_code_candidates", "ALARM_CODE_CONFLICT", normalize_alarm_identifier))
        conflicts.extend(self._indicator_conflicts(items))
        return conflicts

    def _entity_conflicts(self, items, field, conflict_type, normalizer):
        values: dict[str, list[MultimodalEvidenceItem]] = {}
        for item in items:
            if item.confidence < 0.60 and not item.user_confirmed:
                continue
            for raw in getattr(item, field) or []:
                value = normalizer(raw)
                if value:
                    values.setdefault(value, []).append(item)
        if len(values) < 2:
            return []
        confirmed = {value for value, group in values.items() if any(item.user_confirmed for item in group)}
        if conflict_type == "ALARM_CODE_CONFLICT" and not confirmed:
            # Multiple simultaneous alarms are valid unless a confirmed alarm disagrees.
            return []
        evidence_ids = sorted({item.evidence_id for group in values.values() for item in group})
        severity = "HIGH" if confirmed else "MEDIUM"
        question = "检测到设备型号不一致，请确认实际故障设备的完整型号。" if conflict_type.startswith("DEVICE") else "用户确认的告警与识别结果不一致，请核对屏幕上的完整告警代码。"
        return [self._candidate(conflict_type, evidence_ids, severity, question, values)]

    def _indicator_conflicts(self, items):
        values: dict[str, list[MultimodalEvidenceItem]] = {}
        for item in items:
            if item.confidence < 0.60 and not item.user_confirmed:
                continue
            for raw in item.indicator_state_candidates or []:
                value = " ".join(str(raw).lower().split())
                if value:
                    values.setdefault(value, []).append(item)
        if len(values) < 2 or not any(item.user_confirmed for group in values.values() for item in group):
            return []
        evidence_ids = sorted({item.evidence_id for group in values.values() for item in group})
        return [self._candidate(
            "INDICATOR_STATE_CONFLICT", evidence_ids, "MEDIUM",
            "图片与描述中的指示灯状态不一致，请确认颜色以及常亮、闪烁或熄灭状态。", values,
        )]

    @staticmethod
    def _candidate(conflict_type, evidence_ids, severity, question, values):
        seed = json.dumps({"type": conflict_type, "evidence_ids": evidence_ids, "values": sorted(values)}, sort_keys=True)
        return EvidenceConflictCandidate(
            conflict_id=f"mmconf_{hashlib.sha256(seed.encode()).hexdigest()[:24]}",
            conflict_type=conflict_type,
            evidence_ids=evidence_ids,
            severity=severity,
            resolution_required=True,
            recommended_question=question,
        )
