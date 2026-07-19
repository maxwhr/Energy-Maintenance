from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MultimodalMaintenanceCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "multimodal_maintenance_cases"

    case_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_family: Mapped[str | None] = mapped_column(String(128), nullable=True)
    equipment_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alarm_codes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    components: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reported_symptoms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    occurrence_conditions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    user_confirmed_facts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    missing_information: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    clarifying_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    media_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    knowledge_citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    safety_level: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    confidence_status: Mapped[str] = mapped_column(String(32), nullable=False, default="INSUFFICIENT_EVIDENCE")
    diagnosis_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_STARTED")
    sop_draft_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("agent_artifacts.id"), nullable=True)
    task_draft_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("agent_artifacts.id"), nullable=True)
    analysis_job_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_multimodal_cases_status", "status"),
        Index("ix_multimodal_cases_created_by", "created_by"),
        Index("ix_multimodal_cases_device_id", "device_id"),
        Index("ix_multimodal_cases_conversation_id", "conversation_id"),
    )


class MultimodalEvidenceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "multimodal_evidence_items"

    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("multimodal_maintenance_cases.case_id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("uploaded_media.id"), nullable=True)
    ocr_result_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_ocr_results.id"), nullable=True)
    analysis_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("media_ai_analyses.id"), nullable=True)
    frame_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    modality: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    bounding_box: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    page_or_frame_locator: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    device_model_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    alarm_code_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    component_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    indicator_state_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    symptom_candidates: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    observation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contradicted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    contradiction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("case_id", "source_hash", "evidence_type", name="uq_multimodal_evidence_identity"),
        Index("ix_multimodal_evidence_case_id", "case_id"),
        Index("ix_multimodal_evidence_media_id", "media_id"),
        Index("ix_multimodal_evidence_status", "observation_status"),
        Index("ix_multimodal_evidence_region_id", "region_id"),
    )


class MultimodalEvidenceConflict(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "multimodal_evidence_conflicts"

    conflict_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("multimodal_maintenance_cases.case_id", ondelete="CASCADE"), nullable=False
    )
    conflict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    recommended_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_multimodal_conflicts_case_id", "case_id"),
        Index("ix_multimodal_conflicts_status", "resolution_status"),
        Index("ix_multimodal_conflicts_severity", "severity"),
    )


class MultimodalDiagnosticHypothesis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "multimodal_diagnostic_hypotheses"

    hypothesis_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    case_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("multimodal_maintenance_cases.case_id", ondelete="CASCADE"), nullable=False
    )
    fault_category: Mapped[str] = mapped_column(String(64), nullable=False)
    fault_name: Mapped[str] = mapped_column(String(255), nullable=False)
    applicable_device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    required_conditions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    supporting_evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    contradicting_evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    knowledge_citation_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE")
    recommended_checks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    safety_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_information: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        Index("ix_multimodal_hypotheses_case_id", "case_id"),
        Index("ix_multimodal_hypotheses_status", "status"),
        Index("ix_multimodal_hypotheses_fault_category", "fault_category"),
    )
