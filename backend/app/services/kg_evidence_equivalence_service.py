from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KGEvidenceLink, KGEdge, KGNode, KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor


EQUIVALENCE_STATUSES = {
    "EXACT_SUPPORT",
    "PARTIAL_SUPPORT",
    "CONTRADICTED",
    "NOT_FOUND",
    "REQUIRES_REVIEW",
}


@dataclass(frozen=True)
class EvidenceEquivalenceResult:
    evidence_id: UUID
    successor_document_id: UUID | None
    status: str
    supporting_chunk_id: UUID | None
    supporting_semantic_unit_id: UUID | None
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]
    version_difference: dict[str, Any]
    auto_rebind_allowed: bool
    reason: str


class KGEvidenceEquivalenceService:
    """Deterministic current-source support check; no LLM inference is used."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        evidence: KGEvidenceLink,
        successor: KnowledgeDocument | None,
    ) -> EvidenceEquivalenceResult:
        if successor is None:
            return EvidenceEquivalenceResult(
                evidence_id=evidence.id,
                successor_document_id=None,
                status="NOT_FOUND",
                supporting_chunk_id=None,
                supporting_semantic_unit_id=None,
                matched_terms=(),
                missing_terms=(),
                version_difference={},
                auto_rebind_allowed=False,
                reason="no_explicit_current_successor",
            )
        required_terms, relation_required = self._fact_terms(evidence)
        if not required_terms:
            return self._result(evidence, successor, "REQUIRES_REVIEW", None, (), (), "fact_signature_incomplete")
        chunks = list(
            self.db.scalars(
                select(KnowledgeChunk)
                .where(
                    KnowledgeChunk.document_id == successor.id,
                    KnowledgeChunk.status == "active",
                )
                .order_by(KnowledgeChunk.chunk_index.asc())
            )
        )
        best: tuple[KnowledgeChunk | None, tuple[str, ...], tuple[str, ...]] = (None, (), tuple(required_terms))
        for chunk in chunks:
            matched, missing = self.compare_text(chunk.content, required_terms)
            if len(matched) > len(best[1]):
                best = (chunk, matched, missing)
            if not missing and (not relation_required or self._relation_supported(chunk.content, relation_required)):
                anchor_id = self.db.scalar(
                    select(MaintenanceSemanticAnchor.id)
                    .where(
                        MaintenanceSemanticAnchor.source_chunk_id == chunk.id,
                        MaintenanceSemanticAnchor.current_version.is_(True),
                    )
                    .order_by(MaintenanceSemanticAnchor.created_at.desc())
                    .limit(1)
                )
                return EvidenceEquivalenceResult(
                    evidence_id=evidence.id,
                    successor_document_id=successor.id,
                    status="EXACT_SUPPORT",
                    supporting_chunk_id=chunk.id,
                    supporting_semantic_unit_id=anchor_id,
                    matched_terms=matched,
                    missing_terms=missing,
                    version_difference=self._version_difference(evidence, successor),
                    auto_rebind_allowed=True,
                    reason="same_chunk_contains_complete_deterministic_fact_signature",
                )
        chunk, matched, missing = best
        status = "PARTIAL_SUPPORT" if matched else "NOT_FOUND"
        return self._result(
            evidence,
            successor,
            status,
            chunk,
            matched,
            missing,
            "incomplete_fact_signature_in_successor",
        )

    def _result(
        self,
        evidence: KGEvidenceLink,
        successor: KnowledgeDocument,
        status: str,
        chunk: KnowledgeChunk | None,
        matched: tuple[str, ...],
        missing: tuple[str, ...] | str,
        reason: str | None = None,
    ) -> EvidenceEquivalenceResult:
        if isinstance(missing, str):
            reason = missing
            missing_values: tuple[str, ...] = ()
        else:
            missing_values = missing
        return EvidenceEquivalenceResult(
            evidence_id=evidence.id,
            successor_document_id=successor.id,
            status=status,
            supporting_chunk_id=chunk.id if chunk else None,
            supporting_semantic_unit_id=None,
            matched_terms=matched,
            missing_terms=missing_values,
            version_difference=self._version_difference(evidence, successor),
            auto_rebind_allowed=status == "EXACT_SUPPORT",
            reason=reason or "deterministic_equivalence_result",
        )

    def _fact_terms(self, evidence: KGEvidenceLink) -> tuple[list[str], str | None]:
        if evidence.node_id:
            node = self.db.get(KGNode, evidence.node_id)
            if not node:
                return [], None
            values = [node.canonical_name, node.display_name]
            properties = node.properties_json or {}
            values.extend(properties.get(key) for key in ("model", "alarm_code", "component") if properties.get(key))
            return self._unique_terms(values), None
        if evidence.edge_id:
            edge = self.db.get(KGEdge, evidence.edge_id)
            if not edge:
                return [], None
            source = self.db.get(KGNode, edge.source_node_id)
            target = self.db.get(KGNode, edge.target_node_id)
            return self._unique_terms(
                [
                    source.canonical_name if source else None,
                    target.canonical_name if target else None,
                ]
            ), edge.relation_type
        return [], None

    @classmethod
    def compare_text(cls, text_value: str, required_terms: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        normalized = cls._normalize(text_value)
        matched = tuple(term for term in required_terms if cls._normalize(term) in normalized)
        missing = tuple(term for term in required_terms if term not in matched)
        return matched, missing

    @staticmethod
    def _relation_supported(text_value: str, relation_type: str) -> bool:
        normalized = text_value.lower()
        terms = {
            "CAUSED_BY": ("原因", "导致", "caused", "cause"),
            "CHECK_BY": ("检查", "排查", "inspect", "check"),
            "RESOLVED_BY": ("处理", "修复", "replace", "resolve"),
            "HAS_SAFETY_RISK": ("安全", "危险", "risk", "warning"),
            "HAS_FAULT": ("故障", "异常", "fault", "abnormal"),
        }.get(relation_type)
        return True if terms is None else any(term in normalized for term in terms)

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", "", (value or "").lower())

    @classmethod
    def _unique_terms(cls, values: list[str | None]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            cleaned = str(value or "").strip()
            key = cls._normalize(cleaned)
            if len(key) < 2 or key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _version_difference(self, evidence: KGEvidenceLink, successor: KnowledgeDocument) -> dict[str, Any]:
        source = self.db.get(KnowledgeDocument, evidence.document_id) if evidence.document_id else None
        source_metadata = source.metadata_json or {} if source else {}
        successor_metadata = successor.metadata_json or {}
        return {
            "source_version": source_metadata.get("version") or source_metadata.get("document_version"),
            "successor_version": successor_metadata.get("version") or successor_metadata.get("document_version"),
            "product_series_changed": bool(source and source.product_series != successor.product_series),
            "model_changed": bool(source and source.model != successor.model),
            "document_type_changed": bool(source and source.document_type != successor.document_type),
        }
