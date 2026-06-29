from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


ModelProvider = Literal["rule_based", "local_llama_cpp", "cloud_openai"]
ModelTaskType = Literal["qa", "diagnosis", "sop", "summary", "correction", "general"]


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = "user"
    content: str = Field(..., min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message content must not be empty")
        return stripped


class ModelGatewayTestRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=8000)
    messages: list[ModelMessage] | None = None
    provider: ModelProvider | None = None
    task_type: ModelTaskType = "general"
    allow_fallback: bool = True

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_input(self) -> "ModelGatewayTestRequest":
        if not self.prompt and not self.messages:
            raise ValueError("prompt or messages must be provided")
        return self


class ModelGatewayChatRequest(ModelGatewayTestRequest):
    trace_source: str | None = Field(default=None, max_length=128)


class ModelProviderStatus(BaseModel):
    provider: ModelProvider
    enabled: bool
    configured: bool
    available: bool
    availability_status: str = "not_checked"
    model_name: str | None = None
    base_url: str | None = None
    base_url_configured: bool = False
    model_configured: bool = False
    api_type: str | None = None
    api_key_configured: bool = False
    health_path: str | None = None
    latency_ms: int | None = None
    error_summary: str | None = None
    message: str


class ModelGatewayStatus(BaseModel):
    default_provider: ModelProvider
    fallback_enabled: bool
    allow_fallback: bool
    logging_enabled: bool
    timeout_seconds: int
    providers: list[ModelProviderStatus]


class ModelGatewayResponse(BaseModel):
    trace_id: str
    provider: ModelProvider
    requested_provider: ModelProvider
    model_name: str
    task_type: ModelTaskType
    content: str
    success: bool
    fallback_used: bool = False
    latency_ms: int | None = None
    error_message: str | None = None
    usage: dict[str, Any] | None = None


class ModelCallLogRead(BaseModel):
    id: UUID
    trace_id: str | None = None
    module: str | None = None
    provider: str | None = None
    model_name: str | None = None
    call_type: str
    prompt: str | None = None
    response: str | None = None
    latency_ms: int | None = None
    success: bool
    error_message: str | None = None
    created_by: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelCallLogDetail(ModelCallLogRead):
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ModelCallLogPage(BaseModel):
    items: list[ModelCallLogRead]
    total: int
    page: int
    page_size: int
