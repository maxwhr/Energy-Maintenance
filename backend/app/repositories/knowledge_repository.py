from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document

    def update_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        self.db.add(document)
        self.db.flush()
        self.db.refresh(document)
        return document

    def get_document(self, document_id: UUID, *, include_archived: bool = False) -> KnowledgeDocument | None:
        statement = select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        if not include_archived:
            statement = statement.where(KnowledgeDocument.status != "archived")
        return self.db.scalar(statement)

    def get_document_by_title(self, title: str) -> KnowledgeDocument | None:
        statement = select(KnowledgeDocument).where(
            KnowledgeDocument.title == title,
            KnowledgeDocument.status != "archived",
        )
        return self.db.scalar(statement)

    def get_document_by_source_sha256(self, source_sha256: str) -> KnowledgeDocument | None:
        statement = select(KnowledgeDocument).where(
            or_(
                KnowledgeDocument.metadata_json["task28a_source_sha256"].as_string() == source_sha256,
                KnowledgeDocument.source == f"task28a_sha256:{source_sha256}",
            )
        )
        return self.db.scalar(statement)

    def list_documents(
        self,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = None,
        document_type: str | None = None,
        parse_status: str | None = None,
        review_status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeDocument], int]:
        filters = [KnowledgeDocument.status != "archived"]
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series:
            filters.append(KnowledgeDocument.product_series == product_series)
        if device_type:
            filters.append(KnowledgeDocument.device_type == device_type)
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)
        if parse_status:
            filters.append(KnowledgeDocument.parse_status == parse_status)
        if review_status:
            filters.append(KnowledgeDocument.review_status == review_status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.file_name.ilike(pattern),
                    KnowledgeDocument.summary.ilike(pattern),
                    KnowledgeDocument.source.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(KnowledgeDocument).where(*filters)
        list_statement = (
            select(KnowledgeDocument)
            .where(*filters)
            .order_by(KnowledgeDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = self.db.scalar(count_statement) or 0
        documents = list(self.db.scalars(list_statement))
        return documents, total

    def create_chunks(self, chunks: list[KnowledgeChunk]) -> list[KnowledgeChunk]:
        if not chunks:
            return []
        self.db.add_all(chunks)
        self.db.flush()
        return chunks

    def list_chunks_by_document(
        self,
        document_id: UUID,
        *,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeChunk], int]:
        filters = [
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.status == "active",
        ]
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeChunk.content.ilike(pattern),
                    KnowledgeChunk.section_title.ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(KnowledgeChunk).where(*filters)
        list_statement = (
            select(KnowledgeChunk)
            .where(*filters)
            .order_by(KnowledgeChunk.chunk_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        total = self.db.scalar(count_statement) or 0
        chunks = list(self.db.scalars(list_statement))
        return chunks, total

    def delete_chunks_by_document(self, document_id: UUID) -> None:
        chunks = self.db.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        )
        for chunk in chunks:
            self.db.delete(chunk)
        self.db.flush()

    def archive_chunks_by_document(self, document_id: UUID) -> None:
        self.db.execute(
            update(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .values(status="archived")
        )
        self.db.flush()
