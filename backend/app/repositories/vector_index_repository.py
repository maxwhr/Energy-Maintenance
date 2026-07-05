from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument, VectorIndexRun


class VectorIndexRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_run(self, run: VectorIndexRun) -> VectorIndexRun:
        self.db.add(run)
        self.db.flush()
        return run

    def update_run(self, run: VectorIndexRun) -> VectorIndexRun:
        self.db.add(run)
        self.db.flush()
        return run

    def get_run(self, run_id: UUID) -> VectorIndexRun | None:
        return self.db.get(VectorIndexRun, run_id)

    def list_runs(self, *, page: int = 1, page_size: int = 20) -> tuple[list[VectorIndexRun], int]:
        count_statement = select(func.count()).select_from(VectorIndexRun)
        total = int(self.db.scalar(count_statement) or 0)
        statement = (
            select(VectorIndexRun)
            .order_by(VectorIndexRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(statement)), total

    def list_indexes_by_document(self, document_id: UUID) -> list[KnowledgeChunkVectorIndex]:
        statement = (
            select(KnowledgeChunkVectorIndex)
            .where(KnowledgeChunkVectorIndex.document_id == document_id)
            .order_by(KnowledgeChunkVectorIndex.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_indexes_by_chunk(self, chunk_id: UUID) -> list[KnowledgeChunkVectorIndex]:
        statement = (
            select(KnowledgeChunkVectorIndex)
            .where(KnowledgeChunkVectorIndex.chunk_id == chunk_id)
            .order_by(KnowledgeChunkVectorIndex.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_index_for_chunk(
        self,
        chunk_id: UUID,
        *,
        vector_backend: str,
        collection_name: str,
        namespace: str | None,
        embedding_model: str,
        embedding_provider: str,
    ) -> KnowledgeChunkVectorIndex | None:
        statement = select(KnowledgeChunkVectorIndex).where(
            KnowledgeChunkVectorIndex.chunk_id == chunk_id,
            KnowledgeChunkVectorIndex.vector_backend == vector_backend,
            KnowledgeChunkVectorIndex.collection_name == collection_name,
            KnowledgeChunkVectorIndex.namespace == namespace,
            KnowledgeChunkVectorIndex.embedding_model == embedding_model,
            KnowledgeChunkVectorIndex.embedding_provider == embedding_provider,
        )
        return self.db.scalar(statement)

    def list_chunks_for_document(self, document_id: UUID) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.status == "active",
                KnowledgeChunk.status == "active",
            )
            .order_by(KnowledgeChunk.chunk_index.asc())
        )
        return [(row[0], row[1]) for row in self.db.execute(statement).all()]

    def get_chunk_with_document(self, chunk_id: UUID) -> tuple[KnowledgeChunk, KnowledgeDocument] | None:
        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeChunk.id == chunk_id, KnowledgeChunk.status == "active")
        )
        row = self.db.execute(statement).first()
        return (row[0], row[1]) if row else None

    def list_stale_chunks(
        self,
        *,
        vector_backend: str,
        collection_name: str,
        namespace: str | None,
        embedding_model: str,
        embedding_provider: str,
        limit: int,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .outerjoin(
                KnowledgeChunkVectorIndex,
                (KnowledgeChunkVectorIndex.chunk_id == KnowledgeChunk.id)
                & (KnowledgeChunkVectorIndex.vector_backend == vector_backend)
                & (KnowledgeChunkVectorIndex.collection_name == collection_name)
                & (KnowledgeChunkVectorIndex.namespace == namespace)
                & (KnowledgeChunkVectorIndex.embedding_model == embedding_model)
                & (KnowledgeChunkVectorIndex.embedding_provider == embedding_provider)
                & (KnowledgeChunkVectorIndex.index_status == "active"),
            )
            .where(
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.status == "active",
                KnowledgeChunk.status == "active",
                or_(
                    KnowledgeChunkVectorIndex.id.is_(None),
                    KnowledgeChunkVectorIndex.content_hash != KnowledgeChunk.content_hash,
                ),
            )
            .order_by(KnowledgeDocument.created_at.desc(), KnowledgeChunk.chunk_index.asc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in self.db.execute(statement).all()]

    def upsert_index(
        self,
        *,
        chunk: KnowledgeChunk,
        document: KnowledgeDocument,
        vector_backend: str,
        collection_name: str,
        namespace: str | None,
        vector_id: str,
        embedding_model: str,
        embedding_provider: str,
        embedding_dim: int,
        content_hash: str,
        metadata_json: dict,
    ) -> KnowledgeChunkVectorIndex:
        item = self.get_index_for_chunk(
            chunk.id,
            vector_backend=vector_backend,
            collection_name=collection_name,
            namespace=namespace,
            embedding_model=embedding_model,
            embedding_provider=embedding_provider,
        )
        now = datetime.now(timezone.utc)
        if item is None:
            item = KnowledgeChunkVectorIndex(
                chunk_id=chunk.id,
                document_id=document.id,
                vector_backend=vector_backend,
                collection_name=collection_name,
                namespace=namespace,
                vector_id=vector_id,
                embedding_model=embedding_model,
                embedding_provider=embedding_provider,
                embedding_dim=embedding_dim,
                content_hash=content_hash,
                index_status="active",
                last_indexed_at=now,
                metadata_json=metadata_json,
            )
        else:
            item.document_id = document.id
            item.vector_id = vector_id
            item.embedding_dim = embedding_dim
            item.content_hash = content_hash
            item.index_status = "active"
            item.error_message = None
            item.last_indexed_at = now
            item.metadata_json = metadata_json
        self.db.add(item)
        chunk.embedding_status = "embedded"
        self.db.add(chunk)
        self.db.flush()
        return item

    def mark_index_failed(
        self,
        *,
        chunk: KnowledgeChunk,
        document: KnowledgeDocument,
        vector_backend: str,
        collection_name: str,
        namespace: str | None,
        embedding_model: str,
        embedding_provider: str,
        content_hash: str,
        error_message: str,
    ) -> None:
        item = self.get_index_for_chunk(
            chunk.id,
            vector_backend=vector_backend,
            collection_name=collection_name,
            namespace=namespace,
            embedding_model=embedding_model,
            embedding_provider=embedding_provider,
        )
        if item is None:
            item = KnowledgeChunkVectorIndex(
                chunk_id=chunk.id,
                document_id=document.id,
                vector_backend=vector_backend,
                collection_name=collection_name,
                namespace=namespace,
                vector_id=f"failed:{chunk.id}",
                embedding_model=embedding_model,
                embedding_provider=embedding_provider,
                embedding_dim=0,
                content_hash=content_hash,
            )
        item.index_status = "failed"
        item.error_message = error_message[:1000]
        item.last_indexed_at = datetime.now(timezone.utc)
        self.db.add(item)
        chunk.embedding_status = "failed"
        self.db.add(chunk)
        self.db.flush()

    def approved_active_chunks_by_ids(
        self,
        chunk_ids: list[UUID],
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = "pv_inverter",
        document_type: str | None = None,
    ) -> dict[UUID, tuple[KnowledgeChunk, KnowledgeDocument]]:
        if not chunk_ids:
            return {}
        filters = [
            KnowledgeChunk.id.in_(chunk_ids),
            KnowledgeChunk.status == "active",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
        ]
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(KnowledgeDocument.product_series == product_series)
        if device_type:
            filters.append(KnowledgeDocument.device_type == device_type)
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)
        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(*filters)
        )
        return {row[0].id: (row[0], row[1]) for row in self.db.execute(statement).all()}
