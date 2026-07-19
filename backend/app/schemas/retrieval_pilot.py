from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BenchmarkReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "needs_revision"]
    query_valid: bool
    expected_reference_valid: bool
    difficulty_valid: bool
    category_valid: bool
    notes: str = Field(default="", max_length=2000)
    suggested_query: str | None = Field(default=None, max_length=2000)
    suggested_expected_ids: list[UUID] = Field(default_factory=list)
    second_review: bool = False


class BenchmarkFreezeRequest(BaseModel):
    dataset_version: str = Field(default="official_pilot_test_v1", min_length=1, max_length=64)


class OfficialPilotRunRequest(BaseModel):
    dataset_version: str = Field(default="official_pilot_test_v1", min_length=1, max_length=64)


class PilotSessionCreate(BaseModel):
    name: str = Field(default="Task25B-R2 Pilot Session", min_length=1, max_length=255)
    scope_user_ids: list[UUID] = Field(default_factory=list)
    query_prefix: str = Field(default="Task25BR2_", min_length=1, max_length=64)
    retrieval_strategy: Literal["vector", "hybrid", "adaptive"] = "adaptive"


class PilotRollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class PilotIndexRequest(BaseModel):
    allow_real_api: bool = False
    pilot_only: bool = True
    approved_only: bool = True


class PilotReconcileRequest(BaseModel):
    allow_real_api: bool = False


class PilotRouteDecision(BaseModel):
    active: bool = False
    session_id: UUID | None = None
    collection: str | None = None
    retrieval_strategy: str | None = None
    audit_trace_id: str | None = None
    reason: str = "base_route"
    metadata: dict[str, Any] = Field(default_factory=dict)
