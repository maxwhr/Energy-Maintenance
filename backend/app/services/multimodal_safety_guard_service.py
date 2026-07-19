from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from app.models import MultimodalEvidenceItem


HIGH_RISK_TERMS = (
    "高压", "带电", "电池", "直流侧", "熔丝", "开盖", "拆卸", "短路", "过温", "烧蚀", "冒烟", "异味", "漏液", "起火",
)
DANGEROUS_ACTION_TERMS = ("带电操作", "开盖", "拆卸", "更换熔丝", "短接", "旁路", "触碰", "切断线缆")


@dataclass(slots=True)
class MultimodalSafetyDecision:
    safety_level: str
    stop_required: bool
    professional_required: bool
    allowed_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    safety_warnings: list[str] = field(default_factory=list)
    matched_risks: list[str] = field(default_factory=list)
    audit_required: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


class MultimodalSafetyGuardService:
    def evaluate(
        self,
        *,
        evidence_items: Iterable[MultimodalEvidenceItem],
        proposed_actions: list[str],
        valid_safety_citations: list[dict] | None = None,
        device_state_confirmed_safe: bool = False,
    ) -> MultimodalSafetyDecision:
        texts = []
        severe_visual = False
        for item in evidence_items:
            if item.observation_status in {"REJECTED", "CONTRADICTED"}:
                continue
            text = " ".join(filter(None, [item.observed_text, item.normalized_text, *(item.symptom_candidates or [])]))
            texts.append(text)
            if any(term in text for term in ("烧蚀", "冒烟", "漏液", "起火")):
                severe_visual = True
        combined = " ".join([*texts, *proposed_actions])
        risks = [term for term in HIGH_RISK_TERMS if term in combined]
        blocked = []
        allowed = []
        has_safety_source = bool(valid_safety_citations)
        for action in proposed_actions:
            dangerous = any(term in action for term in DANGEROUS_ACTION_TERMS)
            if dangerous and (not device_state_confirmed_safe or not has_safety_source):
                blocked.append(action)
            elif severe_visual and not self._is_stop_action(action):
                blocked.append(action)
            else:
                allowed.append(action)
        stop_required = severe_visual or any(term in risks for term in ("冒烟", "漏液", "起火", "烧蚀"))
        level = "CRITICAL" if stop_required else ("HIGH" if risks else "NORMAL")
        warnings = []
        if stop_required:
            warnings.append("停止操作，隔离现场，并由具备资质的专业人员按官方安全要求处理。")
        elif risks:
            warnings.append("在确认设备已安全隔离、断电并完成残余电压检查前，不得开展拆卸或接触操作。")
        if blocked:
            warnings.append("部分操作因缺少安全状态确认或有效官方安全依据已被阻止。")
        if not warnings:
            warnings.append("检修前确认设备状态、完成安全隔离并遵循适用的官方手册和现场作业制度。")
        return MultimodalSafetyDecision(
            safety_level=level,
            stop_required=stop_required,
            professional_required=bool(risks),
            allowed_actions=list(dict.fromkeys(allowed)),
            blocked_actions=list(dict.fromkeys(blocked)),
            safety_warnings=warnings,
            matched_risks=risks,
            audit_required=bool(risks or blocked),
        )

    @staticmethod
    def _is_stop_action(action: str) -> bool:
        return any(term in action for term in ("停止", "隔离", "撤离", "联系专业人员", "断电"))
