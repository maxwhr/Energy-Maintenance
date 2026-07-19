from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution
from app.services.multimodal_evidence_fusion_service import MultimodalEvidenceFusion
from app.services.multimodal_safety_guard_service import MultimodalSafetyDecision


@dataclass(slots=True)
class DiagnosticHypothesisDraft:
    hypothesis_id: str
    fault_category: str
    fault_name: str
    applicable_device: str | None
    required_conditions: list[str]
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    knowledge_citation_ids: list[str]
    confidence: float
    confidence_level: str
    status: str
    recommended_checks: list[str]
    safety_warnings: list[str]
    missing_information: list[str]


@dataclass(slots=True)
class MultimodalDiagnosisResult:
    observed_facts: list[dict[str, Any]] = field(default_factory=list)
    possible_faults: list[DiagnosticHypothesisDraft] = field(default_factory=list)
    recommended_checks: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    safety_warnings: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    confidence_status: str = "INSUFFICIENT_EVIDENCE"
    unsupported_diagnosis_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultimodalDiagnosisService:
    """Create possibilities only from fused evidence and validated citations."""

    def build(
        self,
        *,
        case_id: str,
        resolution: MultimodalEntityResolution,
        fusion: MultimodalEvidenceFusion,
        citations: list[dict[str, Any]],
        safety: MultimodalSafetyDecision,
        open_conflict_evidence_ids: list[str] | None = None,
    ) -> MultimodalDiagnosisResult:
        valid = [item for item in citations if item.get("chunk_id") and item.get("document_id") and item.get("source_locator")]
        observed = [
            {"evidence_id": item.evidence_id, "level": item.level, "evidence_type": item.evidence_type, "value": item.value}
            for item in [*fusion.confirmed, *fusion.observed]
        ]
        missing = list(resolution.missing_information)
        if not valid:
            missing.append("valid_official_citation")
            return MultimodalDiagnosisResult(
                observed_facts=observed,
                safety_warnings=safety.safety_warnings,
                missing_information=list(dict.fromkeys(missing)),
                citations=[],
                confidence_status="INSUFFICIENT_EVIDENCE",
            )
        support_ids = [item.evidence_id for item in [*fusion.confirmed, *fusion.observed]]
        conflict_ids = list(dict.fromkeys(open_conflict_evidence_ids or []))
        hypotheses = []
        targets = resolution.resolved_alarm_codes or [self._citation_topic(valid[0])]
        for target in targets[:5]:
            related = [item for item in valid if target.casefold() in self._citation_text(item).casefold()]
            if not related:
                related = valid[:1]
            citation_ids = [str(item.get("citation_id") or f"citation:{item['chunk_id']}") for item in related]
            confidence = min(0.90, 0.48 + 0.08 * min(len(support_ids), 3) + 0.08 * min(len(related), 2))
            status = "NEEDS_CLARIFICATION" if conflict_ids or missing else ("SUPPORTED" if support_ids else "CANDIDATE")
            if not support_ids:
                confidence = min(confidence, 0.55)
            name = f"告警 {target} 对应的手册故障场景（待确认）" if target in resolution.resolved_alarm_codes else f"{target}（待确认）"
            seed = json.dumps([case_id, target, citation_ids, support_ids], ensure_ascii=False, sort_keys=True)
            hypotheses.append(DiagnosticHypothesisDraft(
                hypothesis_id=f"mmhyp_{hashlib.sha256(seed.encode()).hexdigest()[:24]}",
                fault_category="alarm_code_query" if target in resolution.resolved_alarm_codes else "maintenance_knowledge_query",
                fault_name=name,
                applicable_device=resolution.resolved_device_model,
                required_conditions=resolution.resolved_conditions,
                supporting_evidence_ids=support_ids,
                contradicting_evidence_ids=conflict_ids,
                knowledge_citation_ids=citation_ids,
                confidence=round(confidence, 4),
                confidence_level="HIGH" if confidence >= 0.8 else ("MEDIUM" if confidence >= 0.6 else "LOW"),
                status=status,
                recommended_checks=[
                    f"按引用章节核对：{item.get('document_title') or '官方手册'} / {item.get('section_title') or '对应章节'}"
                    for item in related[:3]
                ],
                safety_warnings=safety.safety_warnings,
                missing_information=list(dict.fromkeys(missing)),
            ))
        all_checks = list(dict.fromkeys(check for item in hypotheses for check in item.recommended_checks))
        status = "CONFLICTED" if conflict_ids else ("SUPPORTED" if any(item.status == "SUPPORTED" for item in hypotheses) else "PARTIAL")
        return MultimodalDiagnosisResult(
            observed_facts=observed,
            possible_faults=hypotheses,
            recommended_checks=all_checks,
            recommended_actions=safety.allowed_actions,
            safety_warnings=safety.safety_warnings,
            missing_information=list(dict.fromkeys(missing)),
            citations=valid,
            confidence_status=status,
            unsupported_diagnosis_count=0,
        )

    @staticmethod
    def _citation_topic(item: dict[str, Any]) -> str:
        return str(item.get("section_title") or item.get("document_title") or "官方手册相关场景")[:120]

    @staticmethod
    def _citation_text(item: dict[str, Any]) -> str:
        return " ".join(str(item.get(key) or "") for key in ("document_title", "section_title", "quote"))
