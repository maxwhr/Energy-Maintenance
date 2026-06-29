from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import KGEvidenceLink
from app.repositories.knowledge_graph_repository import KnowledgeGraphRepository
from app.schemas.knowledge_graph import KGEvidenceCreate


class KGEvidenceServiceError(ValueError):
    pass


class KGEvidenceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = KnowledgeGraphRepository(db)

    def create_evidence(self, payload: KGEvidenceCreate) -> KGEvidenceLink:
        if not payload.node_id and not payload.edge_id:
            raise KGEvidenceServiceError("Evidence must point to either node_id or edge_id")
        if payload.node_id and not self.repository.get_node(payload.node_id):
            raise KGEvidenceServiceError("Evidence node does not exist")
        if payload.edge_id and not self.repository.get_edge(payload.edge_id):
            raise KGEvidenceServiceError("Evidence edge does not exist")
        evidence = KGEvidenceLink(**payload.model_dump())
        return self.repository.create_evidence(evidence)

    def list_evidence(
        self,
        *,
        node_id: UUID | None = None,
        edge_id: UUID | None = None,
        source_type: str | None = None,
        document_id: UUID | None = None,
        chunk_id: UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        items, total = self.repository.list_evidence(
            node_id=node_id,
            edge_id=edge_id,
            source_type=source_type,
            document_id=document_id,
            chunk_id=chunk_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
