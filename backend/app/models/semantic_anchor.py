from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MaintenanceSemanticAnchor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Isolated source-only semantic anchor mapping for the R3 A/B partition."""

    __tablename__ = "maintenance_semantic_anchors"

    source_chunk_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    anchor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_text: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_retrieval_text: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    semantic_representation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_representation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_locator: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_mode: Mapped[str | None] = mapped_column(String(64))
    current_version: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    vector_id: Mapped[str] = mapped_column(String(256), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    index_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    index_content_hash: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "source_chunk_id", "anchor_type", "semantic_representation_version", "collection_name", "namespace",
            name="uq_semantic_anchor_source_type_version_scope",
        ),
        Index("ix_semantic_anchor_scope", "collection_name", "namespace", "index_status"),
        Index("ix_semantic_anchor_vector", "vector_id"),
        Index("ix_semantic_anchor_source", "source_chunk_id"),
        Index("ix_semantic_anchor_hash", "semantic_representation_hash"),
    )
