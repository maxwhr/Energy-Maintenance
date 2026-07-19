from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.schemas.model_gateway import ModelMessage, ModelProvider, ModelProviderStatus, ModelTaskType


@dataclass(slots=True)
class ModelAdapterRequest:
    prompt: str
    messages: list[ModelMessage]
    model: str | None = None
    task_type: ModelTaskType = "general"
    trace_id: str | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    temperature: float | None = None
    response_format: dict[str, Any] | None = None
    reasoning_effort: str | None = None
    system: str | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: dict[str, Any] | None = None
    required_tool_name: str | None = None
    thinking: dict[str, Any] | None = None
    top_p: float | None = None
    service_tier: str | None = None
    allow_retry: bool = False


@dataclass(slots=True)
class ModelAdapterResponse:
    provider: ModelProvider
    model_name: str
    content: str
    success: bool
    latency_ms: int | None = None
    error_message: str | None = None
    usage: dict[str, Any] | None = None
    raw_payload: dict[str, Any] | None = field(default=None)
    provider_status: str | None = None
    error_code: str | None = None
    provider_request_id: str | None = None
    structured_payload: dict[str, Any] | None = field(default=None)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class ModelAdapter(Protocol):
    provider: ModelProvider
    model_name: str

    def status(self) -> ModelProviderStatus:
        ...

    def chat(self, request: ModelAdapterRequest) -> ModelAdapterResponse:
        ...
