from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeChunkVectorIndex(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_chunk_vector_indexes"

    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    vector_backend: Mapped[str] = mapped_column(String(64), nullable=False, default="dashvector")
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vector_id: Mapped[str] = mapped_column(String(256), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "vector_backend",
            "collection_name",
            "namespace",
            "embedding_model",
            "embedding_provider",
            name="uq_chunk_vector_index_scope",
        ),
        Index("ix_chunk_vector_indexes_chunk_id", "chunk_id"),
        Index("ix_chunk_vector_indexes_document_id", "document_id"),
        Index("ix_chunk_vector_indexes_backend", "vector_backend"),
        Index("ix_chunk_vector_indexes_collection", "collection_name"),
        Index("ix_chunk_vector_indexes_model", "embedding_model"),
        Index("ix_chunk_vector_indexes_provider", "embedding_provider"),
        Index("ix_chunk_vector_indexes_status", "index_status"),
        Index("ix_chunk_vector_indexes_content_hash", "content_hash"),
        Index("ix_chunk_vector_indexes_last_indexed_at", "last_indexed_at"),
    )


class VectorIndexRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vector_index_runs"

    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    vector_backend: Mapped[str] = mapped_column(String(64), nullable=False, default="dashvector")
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    namespace: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    succeeded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_vector_index_runs_run_type", "run_type"),
        Index("ix_vector_index_runs_target", "target_type", "target_id"),
        Index("ix_vector_index_runs_backend", "vector_backend"),
        Index("ix_vector_index_runs_status", "status"),
        Index("ix_vector_index_runs_created_at", "created_at"),
    )
