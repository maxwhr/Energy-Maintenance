from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.model_gateway import ModelMessage, ModelProvider


StructuredOutputMode = Literal["JSON_SCHEMA", "JSON_OBJECT", "PROMPT_ONLY", "MINIMAX_ANTHROPIC_TOOL"]
StructuredExecutionMode = Literal[
    "MINIMAX_ANTHROPIC_TOOL",
    "OPENAI_JSON_SCHEMA",
    "OPENAI_JSON_OBJECT",
    "PROMPT_JSON",
    "DETERMINISTIC_FALLBACK",
]
StructuredParseStrategy = Literal[
    "TOOL_INPUT", "DIRECT_JSON", "CODE_FENCE_JSON", "FIRST_JSON_OBJECT", "FAILED"
]


class StructuredModelRequest(BaseModel):
    purpose: str = Field(min_length=1, max_length=128)
    messages: list[ModelMessage] = Field(min_length=1, max_length=8)
    response_schema: dict[str, Any]
    schema_name: str = Field(min_length=1, max_length=128)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=800, ge=64, le=4096)
    timeout_seconds: float = Field(default=8.0, ge=1.0, le=120.0)
    allow_retry: bool = True
    provider: ModelProvider = "cloud_openai"
    model: str | None = None
    trace_context: dict[str, Any] = Field(default_factory=dict)
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    tool_name: str | None = Field(default=None, min_length=1, max_length=128)
    tool_description: str = Field(default="Submit the validated structured result.", max_length=300)
    top_p: float | None = Field(default=None, gt=0.0, le=1.0)
    service_tier: str | None = Field(default=None, max_length=40)


class StructuredModelResult(BaseModel):
    success: bool
    parsed_payload: dict[str, Any] | None = None
    raw_text_hash: str | None = None
    raw_text_length: int = 0
    raw_top_level_type: str | None = None
    raw_shape: dict[str, Any] = Field(default_factory=dict)
    response_format_mode: StructuredOutputMode
    structured_mode: StructuredExecutionMode = "PROMPT_JSON"
    provider: str = "cloud_openai"
    model: str | None = None
    protocol: str = "openai_compatible"
    parse_strategy: StructuredParseStrategy = "FAILED"
    validation_errors: list[str] = Field(default_factory=list)
    provider_status: str
    provider_error_code: str | None = None
    fallback_reason: str | None = None
    attempt_count: int = 0
    latency_ms: float = 0.0
    trace_id: str
    provider_request_id: str | None = None
    provider_request_id_hash: str | None = None
    tool_name: str | None = None
    tool_use_id_hash: str | None = None
    tool_call_count: int = 0
    tool_input_valid: bool = False
    unexpected_text_block: bool = False
    unexpected_thinking_block: bool = False
    stop_reason: str | None = None
    response_field_names: list[str] = Field(default_factory=list)
    provider_response_meta: dict[str, Any] = Field(default_factory=dict)
