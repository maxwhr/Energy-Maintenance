from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models import UploadedMedia
from app.schemas.media import MediaContextItem
from app.schemas.retrieval import (
    RelatedHistoryItem,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
    RetrievalReference,
    RetrievedChunk,
)
from app.schemas.retrieval_scope import RetrievalScope
from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalDecision
from app.services.citation_validation_service import CitationValidationResult
from app.services.hybrid_retrieval_service import HybridScoredCandidate
from app.services.query_expansion_service import QueryExpansionResult
from app.services.query_understanding_service import QueryUnderstanding
from app.services.vector_index_service import VerifiedVectorHit


class RetrievalPipelineError(ValueError):
    """Publicly handled retrieval-pipeline validation or persistence error."""


@dataclass(slots=True)
class RetrievalPipelineContext:
    """Typed state passed through the retrieval pipeline."""

    request: RetrievalQueryRequest
    resolved_request: RetrievalQueryRequest
    search_request: RetrievalQueryRequest
    retrieval_scope: RetrievalScope | None
    query_understanding: QueryUnderstanding
    expansion: QueryExpansionResult
    strategy_decision: AdaptiveRetrievalDecision
    quality_gate_status: str
    media_items: list[UploadedMedia] = field(default_factory=list)
    query_started: float = 0.0

    keyword_candidates: list[HybridScoredCandidate] = field(default_factory=list)
    vector_candidates: list[VerifiedVectorHit] = field(default_factory=list)
    raw_merged_candidates: list[HybridScoredCandidate] = field(default_factory=list)
    surfaced_candidates: list[HybridScoredCandidate] = field(default_factory=list)
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    references: list[RetrievalReference] = field(default_factory=list)
    citation_validation: CitationValidationResult | None = None

    knowledge_graph_context: dict[str, Any] = field(default_factory=dict)
    related_history: list[RelatedHistoryItem] = field(default_factory=list)
    media_context: list[MediaContextItem] = field(default_factory=list)
    ocr_context: list[dict[str, Any]] = field(default_factory=list)
    media_notice: str | None = None

    vector_enabled: bool = False
    vector_available: bool = False
    vector_fallback_used: bool = False
    quality_fallback_used: bool = False
    quality_fallback_reason: str | None = None
    actual_strategy: str = "keyword"
    insufficient_evidence: bool = False
    abstention_reason: str | None = None

    vector_diagnostics: dict[str, Any] = field(default_factory=dict)
    precision_diagnostics: dict[str, Any] = field(default_factory=dict)
    latency_breakdown: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    response: RetrievalQueryResponse | None = None
