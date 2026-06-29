from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KGNode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kg_nodes"

    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    properties_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    outgoing_edges: Mapped[list["KGEdge"]] = relationship(
        back_populates="source_node",
        foreign_keys="KGEdge.source_node_id",
    )
    incoming_edges: Mapped[list["KGEdge"]] = relationship(
        back_populates="target_node",
        foreign_keys="KGEdge.target_node_id",
    )
    aliases: Mapped[list["KGNodeAlias"]] = relationship(back_populates="node", cascade="all, delete-orphan")
    evidence_links: Mapped[list["KGEvidenceLink"]] = relationship(back_populates="node")

    __table_args__ = (
        UniqueConstraint(
            "node_type",
            "canonical_name",
            "manufacturer",
            "product_series",
            "device_type",
            name="uq_kg_nodes_identity",
        ),
        Index("ix_kg_nodes_node_type", "node_type"),
        Index("ix_kg_nodes_canonical_name", "canonical_name"),
        Index("ix_kg_nodes_manufacturer", "manufacturer"),
        Index("ix_kg_nodes_product_series", "product_series"),
        Index("ix_kg_nodes_device_type", "device_type"),
        Index("ix_kg_nodes_status", "status"),
        Index("ix_kg_nodes_created_at", "created_at"),
    )


class KGEdge(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "kg_edges"

    source_node_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    display_relation: Mapped[str | None] = mapped_column(String(128), nullable=True)
    properties_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    source_node: Mapped[KGNode] = relationship(
        back_populates="outgoing_edges",
        foreign_keys=[source_node_id],
    )
    target_node: Mapped[KGNode] = relationship(
        back_populates="incoming_edges",
        foreign_keys=[target_node_id],
    )
    evidence_links: Mapped[list["KGEvidenceLink"]] = relationship(back_populates="edge")

    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", "relation_type", name="uq_kg_edges_identity"),
        Index("ix_kg_edges_source_node_id", "source_node_id"),
        Index("ix_kg_edges_target_node_id", "target_node_id"),
        Index("ix_kg_edges_relation_type", "relation_type"),
        Index("ix_kg_edges_status", "status"),
        Index("ix_kg_edges_created_at", "created_at"),
    )


class KGNodeAlias(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "kg_node_aliases"

    node_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("kg_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    node: Mapped[KGNode] = relationship(back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("node_id", "normalized_alias", name="uq_kg_node_aliases_node_alias"),
        Index("ix_kg_node_aliases_node_id", "node_id"),
        Index("ix_kg_node_aliases_normalized_alias", "normalized_alias"),
    )


class KGEvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "kg_evidence_links"

    node_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("kg_nodes.id"), nullable=True)
    edge_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("kg_edges.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    document_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("knowledge_documents.id"), nullable=True)
    chunk_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("knowledge_chunks.id"), nullable=True)
    contribution_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("knowledge_contributions.id"), nullable=True)
    diagnosis_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("maintenance_tasks.id"), nullable=True)
    maintenance_record_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("device_maintenance_records.id"),
        nullable=True,
    )
    media_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("uploaded_media.id"), nullable=True)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    node: Mapped[KGNode | None] = relationship(back_populates="evidence_links")
    edge: Mapped[KGEdge | None] = relationship(back_populates="evidence_links")

    __table_args__ = (
        Index("ix_kg_evidence_links_node_id", "node_id"),
        Index("ix_kg_evidence_links_edge_id", "edge_id"),
        Index("ix_kg_evidence_links_source_type", "source_type"),
        Index("ix_kg_evidence_links_source_id", "source_id"),
        Index("ix_kg_evidence_links_document_id", "document_id"),
        Index("ix_kg_evidence_links_chunk_id", "chunk_id"),
        Index("ix_kg_evidence_links_contribution_id", "contribution_id"),
        Index("ix_kg_evidence_links_diagnosis_trace_id", "diagnosis_trace_id"),
        Index("ix_kg_evidence_links_task_id", "task_id"),
        Index("ix_kg_evidence_links_media_id", "media_id"),
        Index("ix_kg_evidence_links_created_at", "created_at"),
    )


class KGExtractionRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "kg_extraction_runs"

    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    extractor: Mapped[str] = mapped_column(String(64), nullable=False, default="rule_based_v1")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    candidates: Mapped[list["KGCandidate"]] = relationship(back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_kg_extraction_runs_source_type", "source_type"),
        Index("ix_kg_extraction_runs_source_id", "source_id"),
        Index("ix_kg_extraction_runs_status", "status"),
        Index("ix_kg_extraction_runs_created_by", "created_by"),
        Index("ix_kg_extraction_runs_created_at", "created_at"),
    )


class KGCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "kg_candidates"

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("kg_extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    evidence_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_node_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("kg_nodes.id"), nullable=True)
    approved_edge_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("kg_edges.id"), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    run: Mapped[KGExtractionRun] = relationship(back_populates="candidates")
    approved_node: Mapped[KGNode | None] = relationship(foreign_keys=[approved_node_id])
    approved_edge: Mapped[KGEdge | None] = relationship(foreign_keys=[approved_edge_id])

    __table_args__ = (
        Index("ix_kg_candidates_run_id", "run_id"),
        Index("ix_kg_candidates_candidate_type", "candidate_type"),
        Index("ix_kg_candidates_status", "status"),
        Index("ix_kg_candidates_reviewed_by", "reviewed_by"),
        Index("ix_kg_candidates_created_at", "created_at"),
    )
