from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.query_understanding import QueryUnderstandingResult
from app.schemas.retrieval_plan import RetrievalPlan


class QueryAwareSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    request_id: str | None = Field(default=None, min_length=1, max_length=128)
    conversation_id: str | None = Field(default=None, max_length=128)
    device_context: dict[str, Any] = Field(default_factory=dict)
    retrieval_mode: Literal["auto", "fast", "deep"] = "auto"
    top_k: int = Field(default=5, ge=1, le=20)
    enable_llm: bool = True
    allow_real_api: bool = False
    persist_result: bool = True

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        return value.strip()


class QueryAwareCandidateRead(BaseModel):
    candidate_id: str
    chunk_id: str
    document_id: str
    document_title: str
    section_title: str | None = None
    page_number: int | None = None
    source_channels: list[str] = Field(default_factory=list)
    source_query_types: list[str] = Field(default_factory=list)
    raw_ranks: dict[str, int] = Field(default_factory=dict)
    raw_scores: dict[str, float] = Field(default_factory=dict)
    rrf_score: float = 0.0
    rerank_score: float | None = None
    final_score: float = 0.0
    exact_model_match: bool = False
    exact_alarm_match: bool = False
    semantic_unit_id: str | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)
    source_locator: dict[str, Any] = Field(default_factory=dict)
    scope_validation_passed: bool = False
    evidence_identity: str | None = None
    evidence_level: str = "CHUNK"
    requested_information_support: list[str] = Field(default_factory=list)
    requested_information_coverage: float = 0.0
    direct_answer_score: float = 0.0
    direct_answer_level: str = "NON_SUPPORTING"
    generality_penalty: float = 0.0
    quote: str = ""


class QueryAwareSearchResponse(BaseModel):
    request_id: str
    conversation_id: str | None = None
    original_query: str
    normalized_query: str
    canonical_question: str
    primary_intent: str
    requested_information: list[str] = Field(default_factory=list)
    confirmed_facts: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    ambiguity: bool = False
    needs_clarification: bool = False
    clarifying_question: str | None = None
    query_understanding_used: bool = False
    query_understanding_fallback: bool = False
    query_understanding_mode: str = "DETERMINISTIC_NORMALIZATION"
    retrieval_plan: RetrievalPlan | None = None
    requested_channels: list[str] = Field(default_factory=list)
    actual_channels: list[str] = Field(default_factory=list)
    executed_channels: list[str] = Field(default_factory=list)
    nonempty_channels: list[str] = Field(default_factory=list)
    failed_channels: list[str] = Field(default_factory=list)
    fallback_channels: list[str] = Field(default_factory=list)
    generated_queries: list[str] = Field(default_factory=list)
    rerank_used: bool = False
    rerank_fallback: bool = False
    confidence_status: str
    retrieval_confidence: float = 0.0
    answer: str = ""
    suggested_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    references: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None
    query_signals: dict[str, Any] = Field(default_factory=dict)
    retrieval_diagnostics: dict[str, Any] = Field(default_factory=dict)
    abstained: bool = False
    message: str = ""
    provider_status: dict[str, Any] = Field(default_factory=dict)
    persistence_status: str = "not_requested"
    qa_record_id: str | None = None
    raw_results: list[QueryAwareCandidateRead] = Field(default_factory=list)
    surfaced_results: list[QueryAwareCandidateRead] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    valid_citations: list[dict[str, Any]] = Field(default_factory=list)
    invalid_citations: list[dict[str, Any]] = Field(default_factory=list)
    citation_validity_ratio: float = 0.0
    citation_coverage_ratio: float = 0.0
    confidence_reason_codes: list[str] = Field(default_factory=list)
    entity_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    evidence_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    structured_model_diagnostics: dict[str, Any] = Field(default_factory=dict)
    model_routing: dict[str, Any] = Field(default_factory=dict)
    minimax_diagnostics: dict[str, Any] = Field(default_factory=dict)
    deterministic_rerank: dict[str, Any] = Field(default_factory=dict)
    minimax_tiebreak: dict[str, Any] = Field(default_factory=dict)
    dedicated_rerank: dict[str, Any] = Field(default_factory=dict)
    post_rerank_constraints: dict[str, Any] = Field(default_factory=dict)
    raw_vector_trace: dict[str, Any] = Field(default_factory=dict)
    rrf_vote_breakdown: dict[str, Any] = Field(default_factory=dict)
    collapse_groups: list[dict[str, Any]] = Field(default_factory=list)
    candidate_channel_counts: dict[str, int] = Field(default_factory=dict)
    stage_latency: dict[str, float] = Field(default_factory=dict)
    scope: str = "huawei_sun2000_competition_v1"
    partition: str = "huawei_sun2000_competition_v1"
    quality_status: str = "DEVELOPMENT_ENGINEERING"
    answer_boundary: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RerankRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    candidate_chunk_ids: list[str] = Field(min_length=1, max_length=20)
    enable_llm: bool = True
    allow_real_api: bool = False
