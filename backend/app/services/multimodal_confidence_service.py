from __future__ import annotations

from dataclasses import dataclass

from app.services.multimodal_evidence_fusion_service import MultimodalEvidenceFusion


@dataclass(slots=True)
class MultimodalConfidenceResult:
    score: float
    status: str
    rationale: list[str]


class MultimodalConfidenceService:
    def calculate(
        self,
        fusion: MultimodalEvidenceFusion,
        *,
        valid_citation_count: int,
        open_high_conflicts: int,
        required_missing_count: int,
    ) -> MultimodalConfidenceResult:
        score = 0.0
        rationale = []
        if fusion.confirmed:
            score += 0.35
            rationale.append("confirmed_evidence_present")
        if fusion.observed:
            score += min(0.20, len(fusion.observed) * 0.05)
            rationale.append("observed_evidence_present")
        if fusion.inferred:
            score += min(0.08, len(fusion.inferred) * 0.02)
            rationale.append("inferred_evidence_limited_weight")
        if valid_citation_count:
            score += min(0.30, valid_citation_count * 0.10)
            rationale.append("official_citation_present")
        if open_high_conflicts:
            score -= min(0.45, open_high_conflicts * 0.25)
            rationale.append("open_high_conflict")
        if required_missing_count:
            score -= min(0.35, required_missing_count * 0.12)
            rationale.append("required_information_missing")
        score = round(max(0.0, min(score, 0.99)), 4)
        if open_high_conflicts:
            status = "CONFLICTED"
        elif required_missing_count or (not fusion.confirmed and not valid_citation_count):
            status = "INSUFFICIENT_EVIDENCE"
        elif score >= 0.75:
            status = "HIGH"
        elif score >= 0.50:
            status = "MEDIUM"
        else:
            status = "LOW"
        return MultimodalConfidenceResult(score, status, rationale)
