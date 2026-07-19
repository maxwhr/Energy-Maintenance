from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MultimodalRetrieveRequest(BaseModel):
    media_id: UUID
    top_k: int = Field(default=5, ge=1, le=10)
    include_manuals: bool = True
    include_cases: bool = True
    include_similar_media: bool = True


class MultimodalScoreBreakdown(BaseModel):
    descriptor_vector_score: float = 0
    ocr_token_score: float = 0
    perceptual_hash_score: float = 0
    difference_hash_score: float = 0
    device_model_exact: float = 0
    fault_code_exact: float = 0
    component_overlap: float = 0
    final_score: float = 0


class MultimodalMatch(BaseModel):
    object_type: Literal["manual", "fault_case", "media"]
    object_id: UUID
    title: str
    score_breakdown: MultimodalScoreBreakdown
    page_number: int | None = None
    section_title: str | None = None
    human_review_required: bool = True


class MultimodalRetrievalResponse(BaseModel):
    media_id: UUID
    capability_label: Literal["descriptor_based_cross_modal"] = "descriptor_based_cross_modal"
    raw_image_embedding: bool = False
    canonical_descriptor: str
    descriptor_embedding_model: str | None = None
    descriptor_embedding_dimension: int | None = None
    manual_matches: list[MultimodalMatch] = Field(default_factory=list)
    case_matches: list[MultimodalMatch] = Field(default_factory=list)
    similar_media: list[MultimodalMatch] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
