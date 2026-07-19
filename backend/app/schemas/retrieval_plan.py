from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RetrievalChannel = Literal["EXACT_KEYWORD", "SCOPED_KEYWORD", "RAW_VECTOR", "SEMANTIC_UNIT", "KG_ALIAS"]
QueryVariantType = Literal[
    "ORIGINAL", "CANONICAL", "SYMPTOM_QUERY", "REQUEST_QUERY", "CONDITION_QUERY",
]


class RetrievalQueryVariant(BaseModel):
    variant_type: QueryVariantType
    query: str
    hypothesis: bool = False
    purpose: str = Field(default="source-faithful retrieval", max_length=160)


class RetrievalPlan(BaseModel):
    original_query: str
    canonical_query: str
    query_variants: list[RetrievalQueryVariant] = Field(default_factory=list, max_length=5)
    requested_channels: list[RetrievalChannel] = Field(default_factory=list)
    channel_queries: dict[str, list[str]] = Field(default_factory=dict)
    channel_weights: dict[str, float] = Field(default_factory=dict)
    query_weights: dict[str, float] = Field(default_factory=dict)
    anchor_types: list[str] = Field(default_factory=list)
    anchor_matrix_version: str = "task25b_r3_dev_r5_r5_anchor_matrix_v1"
    channel_candidate_budgets: dict[str, int] = Field(default_factory=dict)
    per_channel_identity_limit: int = Field(default=60, ge=1, le=100)
    fusion_candidate_limit: int = Field(default=150, ge=50, le=200)
    candidate_top_k: int = Field(default=50, ge=1, le=100)
    rerank_required: bool = False
    clarification_policy: str = "NO_CLARIFICATION"
    required_scope: str = "chinese_engineering_pilot_r2"
    fallback_policy: str = "KEEP_SCOPE_AND_PRESERVE_RRF"
    fast_path: bool = False
    kg_alias_status: str = "DISABLED_DUPLICATE_KEYWORD"


class RetrievalPlanRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    enable_llm: bool = True
