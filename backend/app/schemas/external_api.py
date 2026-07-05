from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


ExternalProviderType = Literal[
    "text_model",
    "vision_model",
    "multimodal_model",
    "ocr_provider",
    "local_model",
    "safety_provider",
    "custom_http",
]
ExternalProviderStatus = Literal["disabled", "not_configured", "blocked", "available", "unavailable", "error"]


class ExternalApiProviderRead(BaseModel):
    id: UUID
    provider_code: str
    provider_name: str
    provider_type: str
    description: str | None = None
    enabled: bool
    requires_api_key: bool
    base_url_env_key: str | None = None
    api_key_env_key: str | None = None
    model_env_key: str | None = None
    default_model_name: str | None = None
    timeout_seconds: int
    max_tokens: int | None = None
    temperature: Decimal | float | None = None
    capabilities_json: list[str] | None = None
    status: str
    status_checked_at: datetime | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExternalApiProviderStatusRead(BaseModel):
    provider_code: str
    provider_name: str
    provider_type: str
    enabled: bool
    configured: bool
    requires_api_key: bool
    status: str
    status_checked_at: datetime | None = None
    capabilities: list[str] = Field(default_factory=list)
    base_url_configured: bool = False
    api_key_configured: bool = False
    model_configured: bool = False
    model_name: str | None = None
    timeout_seconds: int
    message: str


class ExternalApiRouteRead(BaseModel):
    id: UUID
    route_code: str
    agent_code: str | None = None
    tool_name: str | None = None
    capability: str
    primary_provider_code: str
    fallback_provider_codes_json: list[str] | None = None
    allow_fallback: bool
    blocked_when_unconfigured: bool
    safety_policy_json: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExternalApiStatusResponse(BaseModel):
    providers: list[ExternalApiProviderStatusRead]
    routes: list[ExternalApiRouteRead]
    gateway_mode: str = "dry_run_mock_run_and_explicit_real_run"
    real_external_calls_enabled: bool = False


class ExternalApiDryRunRequest(BaseModel):
    capability: str = Field(..., min_length=1, max_length=64)
    provider_code: str | None = Field(default=None, max_length=64)
    route_code: str | None = Field(default=None, max_length=128)
    agent_code: str | None = Field(default=None, max_length=64)
    tool_name: str | None = Field(default=None, max_length=128)
    input_summary: dict[str, Any] = Field(default_factory=dict)

    @field_validator("capability", "provider_code", "route_code", "agent_code", "tool_name")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_target(self) -> "ExternalApiDryRunRequest":
        if not self.provider_code and not self.route_code and not self.tool_name:
            raise ValueError("provider_code, route_code, or tool_name must be provided")
        return self


class ExternalApiMockRunRequest(ExternalApiDryRunRequest):
    mock_run: bool = True


class ExternalApiRealRunRequest(ExternalApiDryRunRequest):
    real_run: bool = False

    @model_validator(mode="after")
    def validate_real_run(self) -> "ExternalApiRealRunRequest":
        if not self.real_run:
            raise ValueError("real_run=true is required for real external API calls")
        return self


class ExternalApiGatewayResult(BaseModel):
    trace_id: str
    status: str
    success: bool
    provider_code: str | None = None
    capability: str
    route_code: str | None = None
    model_name: str | None = None
    would_call: bool = False
    external_api_called: bool = False
    blocked_reason: str | None = None
    message: str
    request_summary: dict[str, Any] = Field(default_factory=dict)
    response_summary: dict[str, Any] = Field(default_factory=dict)
    normalized_result: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int | None = None


class ExternalApiRealCheckRequest(BaseModel):
    provider_code: str = Field(..., min_length=1, max_length=64)
    capability: str = Field(default="status_check", min_length=1, max_length=64)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    real_run: bool = False

    @field_validator("provider_code", "capability")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be empty")
        return stripped

    @model_validator(mode="after")
    def validate_real_run(self) -> "ExternalApiRealCheckRequest":
        if not self.real_run:
            raise ValueError("real_run=true is required for real external API checks")
        return self


class ExternalApiCheckResponse(ExternalApiGatewayResult):
    checked_at: datetime


class ExternalApiCallLogRead(BaseModel):
    id: UUID
    trace_id: str
    provider_code: str
    capability: str
    agent_run_id: str | None = None
    agent_tool_call_id: UUID | None = None
    request_summary_json: dict[str, Any] | None = None
    response_summary_json: dict[str, Any] | None = None
    status: str
    success: bool
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    token_usage_json: dict[str, Any] | None = None
    created_by: UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExternalApiHealthCheckRead(BaseModel):
    id: UUID
    provider_code: str
    status: str
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    checked_at: datetime
    created_by: UUID | None = None

    model_config = {"from_attributes": True}


class ExternalApiPage(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
