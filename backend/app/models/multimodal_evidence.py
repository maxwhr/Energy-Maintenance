from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MediaProcessingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_processing_jobs"

    media_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("uploaded_media.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    external_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_tool_call_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_tool_calls.id"), nullable=True
    )
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_media_processing_jobs_media_id", "media_id"),
        Index("ix_media_processing_jobs_status", "status"),
        Index("ix_media_processing_jobs_job_type", "job_type"),
        Index("ix_media_processing_jobs_provider_code", "provider_code"),
        Index("ix_media_processing_jobs_external_trace_id", "external_trace_id"),
    )


class MediaOCRResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "media_ocr_results"

    media_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("uploaded_media.id"), nullable=False)
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_processing_jobs.id"), nullable=True)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    regions_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    raw_result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_media_ocr_results_media_id", "media_id"),
        Index("ix_media_ocr_results_job_id", "job_id"),
        Index("ix_media_ocr_results_status", "status"),
        Index("ix_media_ocr_results_external_trace_id", "external_trace_id"),
    )


class MediaAIAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_ai_analyses"

    media_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("uploaded_media.id"), nullable=False)
    job_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_processing_jobs.id"), nullable=True)
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    analysis_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_alarm_codes_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    detected_device_info_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    visual_findings_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    possible_faults_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    safety_risks_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    recommended_actions_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    limitations_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    raw_response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    external_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    human_review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reviewed_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_media_ai_analyses_media_id", "media_id"),
        Index("ix_media_ai_analyses_job_id", "job_id"),
        Index("ix_media_ai_analyses_human_review_status", "human_review_status"),
        Index("ix_media_ai_analyses_analysis_type", "analysis_type"),
        Index("ix_media_ai_analyses_external_trace_id", "external_trace_id"),
    )


class MediaEvidenceLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "media_evidence_links"

    media_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("uploaded_media.id"), nullable=False)
    ocr_result_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_ocr_results.id"), nullable=True)
    analysis_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_ai_analyses.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_media_evidence_links_media_id", "media_id"),
        Index("ix_media_evidence_links_source", "source_type", "source_id"),
        Index("ix_media_evidence_links_ocr_result_id", "ocr_result_id"),
        Index("ix_media_evidence_links_analysis_id", "analysis_id"),
    )
