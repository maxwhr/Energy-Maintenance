from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeContribution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_contributions"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    contribution_type: Mapped[str] = mapped_column(String(64), nullable=False, default="experience_summary")
    manufacturer: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, default="pv_inverter")
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_documents.id"),
        nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    device: Mapped["Device | None"] = relationship()
    approved_document: Mapped["KnowledgeDocument | None"] = relationship()
    submitter: Mapped["User | None"] = relationship()
    review_records: Mapped[list["KnowledgeReviewRecord"]] = relationship(back_populates="contribution")

    __table_args__ = (
        Index("ix_knowledge_contributions_review_status", "review_status"),
        Index("ix_knowledge_contributions_submitted_by", "submitted_by"),
        Index("ix_knowledge_contributions_source_trace_id", "source_trace_id"),
        Index("ix_knowledge_contributions_device_id", "device_id"),
    )


class KnowledgeReviewRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_review_records"

    contribution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_contributions.id"),
        nullable=True,
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_documents.id"),
        nullable=True,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_action: Mapped[str] = mapped_column(String(32), nullable=False)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    after_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    contribution: Mapped["KnowledgeContribution | None"] = relationship(back_populates="review_records")
    document: Mapped["KnowledgeDocument | None"] = relationship()
    reviewer: Mapped["User | None"] = relationship()

    __table_args__ = (
        Index("ix_knowledge_review_records_contribution_id", "contribution_id"),
        Index("ix_knowledge_review_records_document_id", "document_id"),
        Index("ix_knowledge_review_records_reviewer_id", "reviewer_id"),
        Index("ix_knowledge_review_records_review_action", "review_action"),
    )


class ModelOutputCorrection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_output_corrections"

    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="qa")
    source_trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    original_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    corrected_output: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")
    approved_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_contribution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_contributions.id"),
        nullable=True,
    )
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    converted_contribution: Mapped["KnowledgeContribution | None"] = relationship()
    submitter: Mapped["User | None"] = relationship(foreign_keys=[submitted_by])
    approver: Mapped["User | None"] = relationship(foreign_keys=[approved_by])

    __table_args__ = (
        Index("ix_model_output_corrections_source_trace_id", "source_trace_id"),
        Index("ix_model_output_corrections_review_status", "review_status"),
        Index("ix_model_output_corrections_source_type", "source_type"),
        Index("ix_model_output_corrections_submitted_by", "submitted_by"),
    )
