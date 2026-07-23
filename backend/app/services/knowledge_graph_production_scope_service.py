from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import KGEvidenceLink, KnowledgeChunk, KnowledgeDocument


# Graph publication is gated by the document's lifecycle review fields, not
# by optional historical metadata.  Older approved documents did not always
# carry normalized_language/approval_mode and must not disappear from a
# source-traceable graph solely for that reason.
PRODUCTION_LANGUAGES = {"zh", "zh-cn", "zh_cn", "chinese"}
NON_PRODUCTION_DOCUMENT_TYPES = {"marketing"}


@dataclass(frozen=True)
class DocumentScopeDecision:
    eligible: bool
    reasons: tuple[str, ...]
    language: str | None
    approval_mode: str | None
    current_version: bool
    superseded_by: str | None


@dataclass
class ProductionScopeEvaluation:
    node_evidence: dict[UUID, list[dict[str, Any]]] = field(default_factory=dict)
    edge_evidence: dict[UUID, list[dict[str, Any]]] = field(default_factory=dict)
    excluded_evidence: list[dict[str, Any]] = field(default_factory=list)

    @property
    def eligible_node_ids(self) -> set[UUID]:
        return {item for item, evidence in self.node_evidence.items() if evidence}

    @property
    def eligible_edge_ids(self) -> set[UUID]:
        return {item for item, evidence in self.edge_evidence.items() if evidence}

    def evidence_for_node(self, node_id: UUID) -> list[dict[str, Any]]:
        return list(self.node_evidence.get(node_id, []))

    def evidence_for_edge(self, edge_id: UUID) -> list[dict[str, Any]]:
        return list(self.edge_evidence.get(edge_id, []))

    def evidence_ids_for_node(self, node_id: UUID) -> list[str]:
        return [str(item["id"]) for item in self.evidence_for_node(node_id)]

    def evidence_ids_for_edge(self, edge_id: UUID) -> list[str]:
        return [str(item["id"]) for item in self.evidence_for_edge(edge_id)]

    def all_evidence(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for group in (*self.node_evidence.values(), *self.edge_evidence.values()):
            for item in group:
                evidence_id = str(item["id"])
                if evidence_id in seen:
                    continue
                seen.add(evidence_id)
                result.append(item)
                if limit is not None and len(result) >= limit:
                    return result
        return result


class KnowledgeGraphProductionScopeService:
    """Evaluates graph facts against their current, approved source evidence."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def classify_document(document: KnowledgeDocument | None) -> DocumentScopeDecision:
        if document is None:
            return DocumentScopeDecision(False, ("document_missing",), None, None, False, None)
        metadata = document.metadata_json or {}
        language = str(metadata.get("normalized_language") or metadata.get("language") or "").strip().lower() or None
        approval_mode = str(metadata.get("approval_mode") or "").strip().lower() or None
        superseded_by = str(metadata.get("superseded_by_document_id") or "").strip() or None
        current_version = bool(metadata.get("current_version", True)) and not superseded_by
        reasons: list[str] = []
        if document.status != "active":
            reasons.append(f"lifecycle_{document.status or 'missing'}")
        if document.review_status != "approved":
            reasons.append(f"approval_{document.review_status or 'missing'}")
        if document.parse_status != "parsed":
            reasons.append(f"parse_{document.parse_status or 'missing'}")
        if (document.document_type or "").lower() in NON_PRODUCTION_DOCUMENT_TYPES:
            reasons.append("marketing_document")
        if not current_version:
            reasons.append("superseded_document")
        return DocumentScopeDecision(
            eligible=not reasons,
            reasons=tuple(reasons),
            language=language,
            approval_mode=approval_mode,
            current_version=current_version,
            superseded_by=superseded_by,
        )

    @classmethod
    def evidence_reasons(
        cls,
        evidence: KGEvidenceLink,
        document: KnowledgeDocument | None,
        chunk: KnowledgeChunk | None,
    ) -> tuple[str, ...]:
        decision = cls.classify_document(document)
        reasons = list(decision.reasons)
        if evidence.document_id is None:
            reasons.append("document_locator_missing")
        if evidence.chunk_id is None:
            reasons.append("chunk_locator_missing")
        elif chunk is None:
            reasons.append("chunk_missing")
        else:
            if document is not None and chunk.document_id != document.id:
                reasons.append("chunk_document_mismatch")
            if chunk.status != "active":
                reasons.append(f"chunk_{chunk.status or 'missing'}")
            if not (chunk.content or "").strip():
                reasons.append("chunk_content_empty")
        return tuple(dict.fromkeys(reasons))

    def evaluate(
        self,
        *,
        node_ids: Iterable[UUID] = (),
        edge_ids: Iterable[UUID] = (),
    ) -> ProductionScopeEvaluation:
        node_values = {item for item in node_ids if item is not None}
        edge_values = {item for item in edge_ids if item is not None}
        result = ProductionScopeEvaluation()
        if not node_values and not edge_values:
            return result
        filters = []
        if node_values:
            filters.append(KGEvidenceLink.node_id.in_(node_values))
        if edge_values:
            filters.append(KGEvidenceLink.edge_id.in_(edge_values))
        statement = (
            select(KGEvidenceLink, KnowledgeDocument, KnowledgeChunk)
            .outerjoin(KnowledgeDocument, KnowledgeDocument.id == KGEvidenceLink.document_id)
            .outerjoin(KnowledgeChunk, KnowledgeChunk.id == KGEvidenceLink.chunk_id)
            .where(or_(*filters))
            .order_by(KGEvidenceLink.created_at.desc())
        )
        for evidence, document, chunk in self.db.execute(statement):
            reasons = self.evidence_reasons(evidence, document, chunk)
            payload = self._evidence_payload(evidence, document, chunk, reasons=reasons)
            if reasons:
                result.excluded_evidence.append(payload)
                continue
            if evidence.node_id is not None:
                result.node_evidence.setdefault(evidence.node_id, []).append(payload)
            if evidence.edge_id is not None:
                result.edge_evidence.setdefault(evidence.edge_id, []).append(payload)
        return result

    @staticmethod
    def _evidence_payload(
        evidence: KGEvidenceLink,
        document: KnowledgeDocument | None,
        chunk: KnowledgeChunk | None,
        *,
        reasons: tuple[str, ...],
    ) -> dict[str, Any]:
        metadata = (chunk.metadata_json or {}) if chunk else {}
        source_locator = metadata.get("source_locator") if isinstance(metadata.get("source_locator"), dict) else {}
        return {
            "id": str(evidence.id),
            "node_id": str(evidence.node_id) if evidence.node_id else None,
            "edge_id": str(evidence.edge_id) if evidence.edge_id else None,
            "source_type": evidence.source_type,
            "source_id": str(evidence.source_id) if evidence.source_id else None,
            "document_id": str(evidence.document_id) if evidence.document_id else None,
            "document_title": document.title if document else None,
            "document_type": document.document_type if document else None,
            "manufacturer": document.manufacturer if document else None,
            "product_series": document.product_series if document else None,
            "chunk_id": str(evidence.chunk_id) if evidence.chunk_id else None,
            "chunk_index": chunk.chunk_index if chunk else None,
            "page_number": chunk.page_number if chunk else None,
            "section_title": chunk.section_title if chunk else None,
            "source_locator": {
                "document_id": str(document.id) if document else None,
                "chunk_id": str(chunk.id) if chunk else None,
                "chunk_index": chunk.chunk_index if chunk else None,
                "page_number": chunk.page_number if chunk else None,
                "section_title": chunk.section_title if chunk else None,
                **source_locator,
            },
            "confidence": evidence.confidence,
            "grounding_status": "GROUNDED_CURRENT" if not reasons else "HISTORICAL_OR_INVALID",
            "scope_status": "CURRENT_VALID" if not reasons else "HISTORICAL_OR_INVALID",
            "scope_reasons": list(reasons),
            "created_at": evidence.created_at,
        }
