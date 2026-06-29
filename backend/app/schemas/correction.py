from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


CorrectionSourceType = Literal["qa", "diagnosis", "sop", "task"]
CorrectionAction = Literal["accept", "reject"]


class CorrectionCreateRequest(BaseModel):
    source_type: CorrectionSourceType = "qa"
    source_trace_id: str = Field(..., min_length=1, max_length=128)
    original_output: dict[str, Any] | str
    corrected_output: dict[str, Any] | str
    reason: str | None = Field(default=None, max_length=2000)
    correction_type: str | None = Field(default="answer_correction", max_length=64)

    @field_validator("source_trace_id", "reason", "correction_type")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CorrectionResolveRequest(BaseModel):
    action: CorrectionAction
    review_comment: str | None = Field(default=None, max_length=2000)

    @field_validator("review_comment")
    @classmethod
    def clean_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CorrectionRead(BaseModel):
    id: UUID
    source_type: str
    source_trace_id: str
    original_output: dict[str, Any]
    corrected_output: dict[str, Any]
    correction_reason: str | None = None
    submitted_by: UUID | None = None
    submitted_by_name: str | None = None
    review_status: str
    approved_by: UUID | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    converted_contribution_id: UUID | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CorrectionPage(BaseModel):
    items: list[CorrectionRead]
    total: int
    page: int
    page_size: int
