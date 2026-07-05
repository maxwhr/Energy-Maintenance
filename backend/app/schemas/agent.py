from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


AgentType = Literal[
    "multimodal_evidence",
    "retrieval_qa",
    "fault_diagnosis",
    "sop_planner",
    "task_orchestration",
    "knowledge_curator",
    "safety_guard",
    "general",
]
AgentToolType = Literal["read", "write", "analysis", "generation", "approval", "safety"]
AgentRiskLevel = Literal["low", "medium", "high"]
AgentRunStatus = Literal["pending", "running", "waiting_approval", "succeeded", "failed", "cancelled", "blocked"]
AgentApprovalStatus = Literal["not_required", "pending", "approved", "rejected", "cancelled"]
AgentConversionTargetType = Literal["knowledge_contribution", "sop_template", "maintenance_task", "kg_candidate"]
AgentConversionStatusValue = Literal["pending", "converting", "succeeded", "failed", "voided"]


class AgentDefinitionRead(BaseModel):
    id: UUID
    agent_code: str
    agent_name: str
    agent_type: str
    description: str | None = None
    enabled: bool
    default_model_provider: str | None = None
    default_model_name: str | None = None
    tool_policy_json: dict[str, Any] | None = None
    safety_policy_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentToolRead(BaseModel):
    id: UUID
    tool_name: str
    tool_display_name: str
    tool_type: str
    description: str | None = None
    enabled: bool
    requires_approval: bool
    allowed_roles_json: list[str] | None = None
    input_schema_json: dict[str, Any] | None = None
    output_schema_json: dict[str, Any] | None = None
    risk_level: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRunCreateRequest(BaseModel):
    agent_code: str = Field(..., min_length=1, max_length=64)
    input_text: str | None = Field(default=None, max_length=4000)
    device_id: UUID | None = None
    input_media_ids: list[UUID] = Field(default_factory=list)
    media_ids: list[UUID] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    tool_names: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    tool_inputs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    requires_approval: bool = False
    dry_run: bool = True
    mock_run: bool = False

    @field_validator("agent_code", "input_text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("input_media_ids", "media_ids")
    @classmethod
    def unique_media_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(values) > 10:
            raise ValueError("media ids supports at most 10 items")
        return list(dict.fromkeys(values))

    @field_validator("tool_names", "tools")
    @classmethod
    def unique_tool_names(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value and value.strip()]
        if len(cleaned) > 16:
            raise ValueError("agent run supports at most 16 tools")
        return list(dict.fromkeys(cleaned))

    def requested_tools(self) -> list[str]:
        return self.tools or self.tool_names

    def requested_media_ids(self) -> list[UUID]:
        combined = [*self.input_media_ids, *self.media_ids]
        return list(dict.fromkeys(combined))


class AgentRunRead(BaseModel):
    id: UUID
    run_id: str
    agent_code: str
    user_id: UUID | None = None
    device_id: UUID | None = None
    status: str
    input_text: str | None = None
    input_media_ids_json: list[UUID] | list[str] | None = None
    context_json: dict[str, Any] | None = None
    provider: str | None = None
    model_name: str | None = None
    final_answer: str | None = None
    confidence: Decimal | float | None = None
    requires_human_approval: bool
    approval_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentStepRead(BaseModel):
    id: UUID
    run_id: str
    step_index: int
    step_type: str
    step_name: str
    status: str
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    reasoning_summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentToolCallRead(BaseModel):
    id: UUID
    run_id: str
    step_id: UUID | None = None
    tool_name: str
    tool_version: str | None = None
    status: str
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentApprovalRead(BaseModel):
    id: UUID
    run_id: str
    approval_type: str
    requested_action: str
    payload_json: dict[str, Any] | None = None
    status: str
    requested_by: UUID | None = None
    reviewed_by: UUID | None = None
    review_comment: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentApprovalActionRequest(BaseModel):
    review_comment: str | None = Field(default=None, max_length=1000)

    @field_validator("review_comment")
    @classmethod
    def strip_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentArtifactRead(BaseModel):
    id: UUID
    run_id: str
    artifact_type: str
    title: str | None = None
    content_text: str | None = None
    content_json: dict[str, Any] | None = None
    source_type: str | None = None
    source_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentEventLogRead(BaseModel):
    id: UUID
    run_id: str | None = None
    event_type: str
    event_message: str | None = None
    payload_json: dict[str, Any] | None = None
    created_by: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentPage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class AgentRunDetail(BaseModel):
    run: AgentRunRead
    steps: list[AgentStepRead] = Field(default_factory=list)
    tool_calls: list[AgentToolCallRead] = Field(default_factory=list)
    approvals: list[AgentApprovalRead] = Field(default_factory=list)
    artifacts: list[AgentArtifactRead] = Field(default_factory=list)


class AgentRunTimeline(AgentRunDetail):
    events: list[AgentEventLogRead] = Field(default_factory=list)


class AgentToolExecuteRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=128)
    input: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True

    @field_validator("tool_name")
    @classmethod
    def strip_tool_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("tool_name is required")
        return stripped


class AgentToolExecuteResponse(BaseModel):
    tool_name: str
    status: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    requires_approval: bool = False
    blocked_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class AgentArtifactConversionRequest(BaseModel):
    target_type: AgentConversionTargetType
    approval_id: UUID | None = None
    override_warnings: bool = False
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def strip_conversion_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class AgentArtifactConversionResult(BaseModel):
    id: UUID | None = None
    conversion_trace_id: str
    source_artifact_id: UUID
    source_artifact_type: str
    source_agent_run_id: str
    approval_id: UUID | None = None
    target_type: AgentConversionTargetType
    target_id: str | None = None
    target_table: str | None = None
    status: str
    conversion_status: str | None = None
    warnings: list[str] = Field(default_factory=list)
    created_records: dict[str, Any] = Field(default_factory=dict)
    message: str
    result_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    already_converted: bool = False
    can_convert: bool = False
    blocked_reason: str | None = None
    converted_by: UUID | None = None
    requested_by: UUID | None = None
    approved_by: UUID | None = None
    voided_by: UUID | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    voided_at: datetime | None = None
    converted_at: datetime | None = None
    error_message: str | None = None


class AgentArtifactConversionStatus(BaseModel):
    source_artifact_id: UUID
    source_artifact_type: str
    source_agent_run_id: str
    allowed_target_types: list[AgentConversionTargetType] = Field(default_factory=list)
    approval_status: str | None = None
    approval_id: UUID | None = None
    conversions: list[AgentArtifactConversionResult] = Field(default_factory=list)
    converted_targets: dict[str, AgentArtifactConversionResult] = Field(default_factory=dict)
    can_convert: bool = False
    already_converted: bool = False
    blocked_reason: str | None = None
    message: str | None = None


class AgentArtifactConversionListItem(AgentArtifactConversionResult):
    pass


class AgentArtifactConversionDetail(AgentArtifactConversionResult):
    source_artifact_snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentArtifactConversionPage(BaseModel):
    items: list[AgentArtifactConversionListItem]
    total: int
    page: int
    page_size: int


class AgentArtifactConversionHistoryFilter(BaseModel):
    source_run_id: UUID | None = None
    source_artifact_id: UUID | None = None
    target_type: AgentConversionTargetType | None = None
    conversion_status: AgentConversionStatusValue | None = None


class AgentArtifactConversionVoidRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
