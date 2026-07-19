from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from app.models import MultimodalEvidenceItem


@dataclass(slots=True)
class FusedEvidence:
    evidence_id: str
    level: str
    evidence_type: str
    value: str | None
    confidence: float
    source_type: str
    media_id: str | None
    locator: dict[str, Any]
    contradicted: bool = False


@dataclass(slots=True)
class MultimodalEvidenceFusion:
    confirmed: list[FusedEvidence] = field(default_factory=list)
    observed: list[FusedEvidence] = field(default_factory=list)
    inferred: list[FusedEvidence] = field(default_factory=list)
    knowledge_supported: list[FusedEvidence] = field(default_factory=list)
    rejected_or_contradicted: list[str] = field(default_factory=list)
    deduplicated_count: int = 0
    source_vote_caps_applied: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class MultimodalEvidenceFusionService:
    def fuse(self, evidence_items: Iterable[MultimodalEvidenceItem]) -> MultimodalEvidenceFusion:
        result = MultimodalEvidenceFusion()
        identities: set[tuple] = set()
        source_votes: dict[tuple[str, str, str], int] = {}
        for item in evidence_items:
            if item.observation_status in {"REJECTED", "CONTRADICTED"} or item.contradicted:
                result.rejected_or_contradicted.append(item.evidence_id)
                continue
            value = item.normalized_text or item.observed_text
            identity = (
                item.evidence_type,
                (value or "").casefold(),
                str(item.media_id or ""),
                item.region_id or "",
            )
            if identity in identities:
                result.deduplicated_count += 1
                continue
            identities.add(identity)
            vote_key = (str(item.media_id or "none"), item.source_type, item.evidence_type)
            source_votes[vote_key] = source_votes.get(vote_key, 0) + 1
            if source_votes[vote_key] > 5:
                result.source_vote_caps_applied += 1
                continue
            fused = FusedEvidence(
                evidence_id=item.evidence_id,
                level=self._level(item),
                evidence_type=item.evidence_type,
                value=value,
                confidence=float(item.confidence),
                source_type=item.source_type,
                media_id=str(item.media_id) if item.media_id else None,
                locator=item.page_or_frame_locator or {},
            )
            getattr(result, self._bucket(fused.level)).append(fused)
        return result

    @staticmethod
    def _level(item: MultimodalEvidenceItem) -> str:
        if item.source_type == "OFFICIAL_KNOWLEDGE":
            return "KNOWLEDGE_SUPPORTED"
        if item.user_confirmed or item.observation_status == "USER_CONFIRMED":
            return "CONFIRMED"
        metadata = item.metadata_json or {}
        if (
            item.source_type == "OCR_PROVIDER"
            and item.evidence_type in {"DEVICE_MODEL", "ALARM_CODE"}
            and float(item.confidence) >= 0.85
            and metadata.get("official_match_valid") is True
        ):
            return "CONFIRMED"
        if item.source_type == "MULTIMODAL_PROVIDER" or item.observation_status == "INFERRED":
            return "INFERRED"
        return "OBSERVED"

    @staticmethod
    def _bucket(level: str) -> str:
        return {
            "CONFIRMED": "confirmed",
            "OBSERVED": "observed",
            "INFERRED": "inferred",
            "KNOWLEDGE_SUPPORTED": "knowledge_supported",
        }[level]
