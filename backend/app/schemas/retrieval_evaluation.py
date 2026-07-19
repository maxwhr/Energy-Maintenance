from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EvaluationEvidenceIdentity(BaseModel):
    """Frozen hierarchy-aware relevance label used only by evaluation."""

    case_id: str = Field(min_length=1, max_length=128)
    evaluation_level: Literal["CHUNK", "SEMANTIC_UNIT", "SECTION", "DOCUMENT"]
    expected_semantic_unit_ids: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[str] = Field(default_factory=list)
    expected_section_ids: list[str] = Field(default_factory=list)
    expected_document_ids: list[str] = Field(default_factory=list)
    direct_evidence_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    background_evidence_ids: list[str] = Field(default_factory=list)
    source_locator: dict[str, Any] = Field(default_factory=dict)
    relevance_grades: dict[str, Literal[0, 1, 2, 3]] = Field(default_factory=dict)
    label_reason: str = Field(min_length=1)
    label_version: str = Field(min_length=1, max_length=128)

    def relevant_ids(self) -> set[str]:
        return set(self.direct_evidence_ids) | set(self.supporting_evidence_ids) | set(self.background_evidence_ids)

    @model_validator(mode="after")
    def validate_grounded_identity(self):
        if self.relevant_ids() and not self.source_locator:
            raise ValueError("relevant evaluation evidence requires a source locator")
        if any(value not in {0, 1, 2, 3} for value in self.relevance_grades.values()):
            raise ValueError("relevance grades must be in 0..3")
        return self


class RetrievalEvaluationCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=64)
    query_text: str = Field(min_length=1, max_length=2000)
    query_media_id: UUID | None = None
    expected_document_ids: list[UUID] = Field(default_factory=list)
    expected_chunk_ids: list[UUID] = Field(default_factory=list)
    expected_media_ids: list[UUID] = Field(default_factory=list)
    required_filters: dict[str, Any] = Field(default_factory=dict)
    excluded_document_ids: list[UUID] = Field(default_factory=list)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    dataset_split: Literal["train", "dev", "test"]
    review_status: Literal["draft", "engineering_verified", "expert_verified", "rejected"] = "draft"
    source_type: str = Field(min_length=1, max_length=64)
    metadata_json: dict[str, Any] | None = None


class RetrievalEvaluationRequest(BaseModel):
    name: str = Field(default="Task25B retrieval evaluation", min_length=1, max_length=255)
    dataset_split: Literal["dev", "test", "test_v2", "test_v3"] = "test"
    modes: list[Literal["keyword", "vector", "hybrid", "hybrid_rerank", "adaptive", "multimodal_descriptor", "similar_media"]] = Field(
        default_factory=lambda: ["keyword", "vector", "hybrid", "hybrid_rerank"]
    )
    max_cases: int = Field(default=100, ge=1, le=500)
    dataset_version: str = Field(default="task25b-v1", max_length=64)
