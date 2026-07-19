from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceIdentity:
    primary_id: str
    equivalence_key: str
    aliases: frozenset[str]
    level: str


class EvidenceIdentityService:
    """Give Chunk/Section/Semantic Unit candidates a common source-grounded identity."""

    VERSION = "task25b_r3_dev_r5_r5_evidence_identity_v1"

    @staticmethod
    def _section_id(document_id: str, locator: dict[str, Any], section_title: str | None) -> str | None:
        section = locator.get("heading_path") or locator.get("section") or locator.get("html_anchor") or section_title
        if not section:
            return None
        serialized = json.dumps(section, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"section:{document_id}:{digest}"

    def identify(self, candidate: Any) -> EvidenceIdentity:
        semantic = str(getattr(candidate, "semantic_unit_id", None) or "")
        chunk_id = str(getattr(candidate, "chunk_id", "") or "")
        document_id = str(getattr(candidate, "document_id", "") or "")
        source_chunks = list(dict.fromkeys(
            str(value) for value in (getattr(candidate, "source_chunk_ids", None) or [chunk_id]) if value
        ))
        locator = dict(getattr(candidate, "source_locator", None) or {})
        section_id = self._section_id(document_id, locator, getattr(candidate, "section_title", None))
        aliases = {chunk_id, *source_chunks}
        if semantic:
            aliases.update({semantic, f"su:{semantic}"})
            primary = semantic
            level = "SEMANTIC_UNIT"
        elif section_id:
            aliases.add(section_id)
            primary = section_id
            level = "SECTION"
        else:
            primary = chunk_id
            level = "CHUNK"
        aliases.discard("")
        if source_chunks:
            source_digest = hashlib.sha256("|".join(sorted(source_chunks)).encode("utf-8")).hexdigest()[:20]
            equivalence = f"source_group:{source_digest}"
        else:
            equivalence = primary
        return EvidenceIdentity(primary, equivalence, frozenset(aliases), level)

    def apply(self, candidate: Any) -> EvidenceIdentity:
        identity = self.identify(candidate)
        candidate.evidence_identity = identity.primary_id
        candidate.evidence_equivalence_key = identity.equivalence_key
        candidate.evidence_aliases = set(identity.aliases)
        candidate.evidence_level = identity.level
        return identity

    @staticmethod
    def evaluation_match(candidate: Any, expected_ids: set[str]) -> bool:
        aliases = set(getattr(candidate, "evidence_aliases", None) or [])
        aliases.update({
            str(getattr(candidate, "candidate_id", "") or ""),
            str(getattr(candidate, "chunk_id", "") or ""),
            str(getattr(candidate, "semantic_unit_id", "") or ""),
            *(str(value) for value in getattr(candidate, "source_chunk_ids", None) or []),
        })
        semantic = str(getattr(candidate, "semantic_unit_id", "") or "")
        if semantic:
            aliases.add(f"su:{semantic}")
        aliases.discard("")
        return bool(aliases & expected_ids)
