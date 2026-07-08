from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Protocol

from app.schemas.model_gateway import ModelMessage, ModelProvider, ModelProviderStatus, ModelTaskType


@dataclass(slots=True)
class ModelAdapterRequest:
    prompt: str
    messages: list[ModelMessage]
    task_type: ModelTaskType = "general"
    trace_id: str | None = None


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


class ModelAdapter(Protocol):
    provider: ModelProvider
    model_name: str

    def status(self) -> ModelProviderStatus:
        ...

    def chat(self, request: ModelAdapterRequest) -> ModelAdapterResponse:
        ...

    def stream_chat(self, request: ModelAdapterRequest) -> Iterator[str]:
        ...
