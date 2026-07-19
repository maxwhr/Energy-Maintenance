from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.semantic_anchor import MaintenanceSemanticAnchor


class SemanticAnchorRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, *, source_chunk_id: UUID, anchor_type: str, version: str, collection: str, namespace: str) -> MaintenanceSemanticAnchor | None:
        return self.db.scalar(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.source_chunk_id == source_chunk_id,
            MaintenanceSemanticAnchor.anchor_type == anchor_type,
            MaintenanceSemanticAnchor.semantic_representation_version == version,
            MaintenanceSemanticAnchor.collection_name == collection,
            MaintenanceSemanticAnchor.namespace == namespace,
        ))

    def list_scope(self, *, collection: str, namespace: str, source_chunk_ids: list[UUID] | None = None) -> list[MaintenanceSemanticAnchor]:
        statement = select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.collection_name == collection,
            MaintenanceSemanticAnchor.namespace == namespace,
        )
        if source_chunk_ids is not None:
            statement = statement.where(MaintenanceSemanticAnchor.source_chunk_id.in_(source_chunk_ids))
        return list(self.db.scalars(statement.order_by(MaintenanceSemanticAnchor.source_chunk_id, MaintenanceSemanticAnchor.anchor_type)))

    def by_vector_ids(self, *, collection: str, namespace: str, vector_ids: list[str]) -> dict[str, MaintenanceSemanticAnchor]:
        if not vector_ids:
            return {}
        rows = self.db.scalars(select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.collection_name == collection,
            MaintenanceSemanticAnchor.namespace == namespace,
            MaintenanceSemanticAnchor.vector_id.in_(vector_ids),
            MaintenanceSemanticAnchor.index_status == "active",
        ))
        return {row.vector_id: row for row in rows}

    def save(self, anchor: MaintenanceSemanticAnchor) -> MaintenanceSemanticAnchor:
        self.db.add(anchor)
        self.db.flush()
        return anchor
