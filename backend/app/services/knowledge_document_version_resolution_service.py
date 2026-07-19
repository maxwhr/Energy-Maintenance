from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument
from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService


EXPLICIT_PREDECESSOR_KEYS = (
    "supersedes_document_id",
    "previous_document_id",
    "replaces_document_id",
)


@dataclass(frozen=True)
class DocumentVersionResolution:
    archived_document_id: UUID
    current_successor_document_id: UUID | None
    version_chain: tuple[UUID, ...]
    replacement_reason: str
    current_status: str | None
    approval_status: str | None
    language: str | None
    document_category: str | None
    confidence: float
    resolution_status: str
    title_similarity_candidates: tuple[dict[str, Any], ...]


class KnowledgeDocumentVersionResolutionService:
    """Resolves only explicit document-version relations; title similarity is advisory."""

    def __init__(self, db: Session):
        self.db = db

    def resolve(self, document: KnowledgeDocument) -> DocumentVersionResolution:
        explicit = self._explicit_successors(document)
        valid = [candidate for candidate in explicit if self._valid_successor(candidate)]
        successor = valid[0] if len(valid) == 1 else None
        candidates = self._similarity_candidates(document, excluded={item.id for item in explicit})
        if successor is not None:
            metadata = successor.metadata_json or {}
            return DocumentVersionResolution(
                archived_document_id=document.id,
                current_successor_document_id=successor.id,
                version_chain=(document.id, successor.id),
                replacement_reason="explicit_version_relation",
                current_status=successor.status,
                approval_status=successor.review_status,
                language=str(metadata.get("normalized_language") or metadata.get("language") or "") or None,
                document_category=successor.document_type,
                confidence=1.0,
                resolution_status="EXACT_SUCCESSOR",
                title_similarity_candidates=tuple(candidates),
            )
        status = "AMBIGUOUS_EXPLICIT_SUCCESSOR" if len(valid) > 1 else "NO_EXPLICIT_CURRENT_SUCCESSOR"
        reason = "multiple_valid_explicit_relations" if len(valid) > 1 else "no_valid_explicit_version_relation"
        return DocumentVersionResolution(
            archived_document_id=document.id,
            current_successor_document_id=None,
            version_chain=(document.id, *tuple(item.id for item in explicit)),
            replacement_reason=reason,
            current_status=None,
            approval_status=None,
            language=None,
            document_category=None,
            confidence=0.0,
            resolution_status=status,
            title_similarity_candidates=tuple(candidates),
        )

    def _explicit_successors(self, document: KnowledgeDocument) -> list[KnowledgeDocument]:
        metadata = document.metadata_json or {}
        ids: set[UUID] = set()
        direct = metadata.get("superseded_by_document_id")
        if direct:
            try:
                ids.add(UUID(str(direct)))
            except ValueError:
                pass
        reverse_filters = [
            KnowledgeDocument.metadata_json[key].as_string() == str(document.id)
            for key in EXPLICIT_PREDECESSOR_KEYS
        ]
        if reverse_filters:
            ids.update(self.db.scalars(select(KnowledgeDocument.id).where(or_(*reverse_filters))))
        if not ids:
            return []
        return list(self.db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(ids))))

    @staticmethod
    def _valid_successor(document: KnowledgeDocument) -> bool:
        decision = KnowledgeGraphProductionScopeService.classify_document(document)
        return decision.eligible and document.document_type != "marketing"

    def _similarity_candidates(
        self,
        document: KnowledgeDocument,
        *,
        excluded: set[UUID],
    ) -> list[dict[str, Any]]:
        statement = select(KnowledgeDocument).where(
            KnowledgeDocument.id != document.id,
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.manufacturer == document.manufacturer,
            KnowledgeDocument.document_type == document.document_type,
        )
        candidates = []
        for item in self.db.scalars(statement):
            if item.id in excluded or not self._valid_successor(item):
                continue
            score = self._candidate_score(document, item)
            if score <= 0:
                continue
            candidates.append(
                {
                    "document_id": str(item.id),
                    "score": round(score, 6),
                    "product_series_match": item.product_series == document.product_series,
                    "model_match": bool(item.model and document.model and item.model == document.model),
                    "auto_bind_allowed": False,
                    "reason": "title_similarity_is_candidate_only",
                }
            )
        return sorted(candidates, key=lambda value: (-float(value["score"]), value["document_id"]))[:10]

    @classmethod
    def _candidate_score(cls, source: KnowledgeDocument, target: KnowledgeDocument) -> float:
        source_terms = cls._title_terms(source.title)
        target_terms = cls._title_terms(target.title)
        union = source_terms | target_terms
        title_score = len(source_terms & target_terms) / len(union) if union else 0.0
        return min(
            1.0,
            title_score * 0.6
            + (0.25 if source.product_series and source.product_series == target.product_series else 0.0)
            + (0.15 if source.model and source.model == target.model else 0.0),
        )

    @staticmethod
    def _title_terms(value: str) -> set[str]:
        return {item.lower() for item in re.findall(r"[A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", value or "")}

