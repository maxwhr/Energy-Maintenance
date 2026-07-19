from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RetrievalEvaluationCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_evaluation_cases"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_media_id: Mapped[UUID | None] = mapped_column(ForeignKey("uploaded_media.id", ondelete="SET NULL"))
    expected_document_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expected_chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    expected_media_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    excluded_document_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    dataset_split: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("ix_retrieval_eval_cases_category", "category"),
        Index("ix_retrieval_eval_cases_split", "dataset_split"),
        Index("ix_retrieval_eval_cases_review", "review_status"),
        Index("ix_retrieval_eval_cases_source", "source_type"),
    )


class RetrievalEvaluationRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retrieval_evaluation_runs"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_backend: Mapped[str] = mapped_column(String(64), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    retrieval_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics_json: Mapped[dict | None] = mapped_column(JSONB)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_retrieval_eval_runs_status", "run_status"),
        Index("ix_retrieval_eval_runs_dataset", "dataset_version"),
        Index("ix_retrieval_eval_runs_created", "created_at"),
    )


class RetrievalEvaluationResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retrieval_evaluation_results"

    run_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("retrieval_evaluation_cases.id", ondelete="CASCADE"), nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(64), nullable=False)
    ranked_document_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ranked_chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ranked_media_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    score_breakdown_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    recall_at_5: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    recall_at_10: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    reciprocal_rank: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ndcg_at_10: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    precision_at_5: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("run_id", "case_id", "retrieval_mode", name="uq_retrieval_eval_result_scope"),
        Index("ix_retrieval_eval_results_run", "run_id"),
        Index("ix_retrieval_eval_results_case", "case_id"),
        Index("ix_retrieval_eval_results_mode", "retrieval_mode"),
    )


class RetrievalDatasetFreeze(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_dataset_freezes"

    dataset_version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    dataset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False)
    freeze_status: Mapped[str] = mapped_column(String(32), nullable=False, default="frozen")
    frozen_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    unfrozen_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    unfrozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unfreeze_reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_retrieval_dataset_freezes_status", "freeze_status"),
        Index("ix_retrieval_dataset_freezes_type", "dataset_type"),
    )


class RetrievalOfficialRunLock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "retrieval_official_run_locks"

    dataset_freeze_id: Mapped[UUID] = mapped_column(
        ForeignKey("retrieval_dataset_freezes.id", ondelete="RESTRICT"), nullable=False
    )
    run_purpose: Mapped[str] = mapped_column(String(64), nullable=False)
    official_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("retrieval_evaluation_runs.id", ondelete="RESTRICT")
    )
    lock_status: Mapped[str] = mapped_column(String(32), nullable=False, default="locked")
    locked_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    unlock_requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    unlock_reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("dataset_freeze_id", "run_purpose", name="uq_retrieval_official_run_lock_scope"),
        Index("ix_retrieval_official_run_locks_status", "lock_status"),
        Index("ix_retrieval_official_run_locks_freeze", "dataset_freeze_id"),
    )


class MediaSimilarityFeature(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_similarity_features"

    media_id: Mapped[UUID] = mapped_column(ForeignKey("uploaded_media.id", ondelete="CASCADE"), nullable=False, unique=True)
    perceptual_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    difference_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    ocr_normalized_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visual_descriptor: Mapped[str] = mapped_column(Text, nullable=False)
    device_model: Mapped[str | None] = mapped_column(String(128))
    fault_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    component_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    vector_index_id: Mapped[str | None] = mapped_column(String(256))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_media_similarity_features_status", "feature_status"),
        Index("ix_media_similarity_features_hash", "content_hash"),
        Index("ix_media_similarity_features_model", "device_model"),
    )
