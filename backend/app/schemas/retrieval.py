from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.media import MediaContextItem


ALLOWED_MANUFACTURERS = {"huawei", "sungrow"}
ALLOWED_PRODUCT_SERIES = {"SUN2000", "FusionSolar", "SG", "other"}
ALLOWED_DEVICE_TYPES = {"pv_inverter"}
ALLOWED_DOCUMENT_TYPES = {
    "manual",
    "alarm_code",
    "sop",
    "fault_case",
    "inspection_standard",
    "maintenance_record",
}


class RetrievalQueryRequest(BaseModel):
    query: str | None = Field(default=None, max_length=2000)
    question: str | None = Field(default=None, max_length=2000)
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    device_id: UUID | None = None
    document_type: str | None = None
    fault_type: str | None = None
    alarm_code: str | None = Field(default=None, max_length=64)
    media_ids: list[UUID] = Field(default_factory=list)
    use_ocr_text: bool = False
    top_k: int = 5
    include_history: bool = True
    enable_vector_search: bool = True
    enable_kg_enhancement: bool = True
    enable_model_enhancement: bool = False
    model_provider: str = "rule_based"
    allow_model_fallback: bool = True
    retrieval_mode: Literal["keyword", "vector", "hybrid"] = "hybrid"
    enable_vector: bool = True
    vector_top_k: int = 8
    hybrid_keyword_weight: float = 0.35
    hybrid_vector_weight: float = 0.65
    min_score: float = 0.20

    @field_validator("query", "question", "manufacturer", "product_series", "device_type", "document_type", "fault_type", "alarm_code", "model_provider")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @property
    def normalized_question(self) -> str:
        return (self.question or self.query or "").strip()

    @field_validator("media_ids")
    @classmethod
    def validate_media_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) > 10:
            raise ValueError("media_ids supports at most 10 media items")
        return list(dict.fromkeys(values))


class RetrievalReference(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    quote: str
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    document_type: str | None = None
    source: str | None = None
    score: float


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    chunk_index: int
    section_title: str | None = None
    page_number: int | None = None
    content: str
    score: float
    manufacturer: str
    product_series: str | None = None
    device_type: str
    document_type: str
    source: str | None = None
    created_at: datetime
    keyword_score: float | None = None
    vector_score: float | None = None
    hybrid_score: float | None = None
    retrieval_source: Literal["keyword", "vector", "hybrid"] = "keyword"
    vector_backend: str | None = None


class RelatedHistoryItem(BaseModel):
    record_id: UUID
    device_id: UUID
    fault_type: str | None = None
    alarm_code: str | None = None
    fault_description: str | None = None
    root_cause: str | None = None
    repair_action: str | None = None
    verification_result: str | None = None
    is_recurrent: bool
    completed_at: datetime | None = None


class RetrievalQueryAnalysis(BaseModel):
    normalized_query: str
    keywords: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)


class RetrievalQueryResponse(BaseModel):
    trace_id: str
    question: str
    answer: str
    suggested_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    references: list[RetrievalReference] = Field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    related_history: list[RelatedHistoryItem] = Field(default_factory=list)
    media_items: list[MediaContextItem] = Field(default_factory=list)
    media_notice: str | None = None
    ocr_context: list[dict[str, Any]] = Field(default_factory=list)
    kg_context: dict[str, Any] = Field(default_factory=dict)
    kg_nodes: list[dict[str, Any]] = Field(default_factory=list)
    kg_edges: list[dict[str, Any]] = Field(default_factory=list)
    kg_evidence: list[dict[str, Any]] = Field(default_factory=list)
    kg_paths: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.1
    model_provider: str = "rule_based"
    model_name: str = "keyword_retrieval_v1"
    model_enhanced: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    model_call_trace_id: str | None = None
    retrieval_mode: str = "keyword"
    vector_enabled: bool = False
    vector_available: bool = False
    hybrid_used: bool = False
    vector_fallback_used: bool = False
    vector_backend: str = "unavailable"
    embedding_provider: str | None = None
    embedding_model: str | None = None
    retrieval_diagnostics: dict[str, Any] = Field(default_factory=dict)
    query_analysis: RetrievalQueryAnalysis | None = None


class RetrievalRecordListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class RetrievalRecordDetail(BaseModel):
    record: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
