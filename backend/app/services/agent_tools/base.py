from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import User


AGENT_TOOL_STATUSES = {"succeeded", "failed", "blocked", "skipped", "waiting_approval"}


@dataclass(slots=True)
class AgentToolExecutionContext:
    db: Session
    current_user: User
    run_id: str
    device_id: UUID | None = None
    media_ids: list[UUID] = field(default_factory=list)
    dry_run: bool = True
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentToolResult:
    tool_name: str
    status: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    requires_approval: bool = False
    blocked_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in AGENT_TOOL_STATUSES:
            raise ValueError(f"Unsupported agent tool status: {self.status}")

    def to_output(self) -> dict[str, Any]:
        return json_safe(
            {
                "tool_name": self.tool_name,
                "status": self.status,
                "summary": self.summary,
                "data": self.data,
                "evidence": self.evidence,
                "requires_approval": self.requires_approval,
                "blocked_reason": self.blocked_reason,
                "error_code": self.error_code,
                "error_message": self.error_message,
            }
        )


class BaseAgentTool:
    tool_name: str = ""

    def execute(self, payload: dict[str, Any], context: AgentToolExecutionContext) -> AgentToolResult:
        raise NotImplementedError

    @staticmethod
    def text(payload: dict[str, Any], *keys: str, default: str = "") -> str:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return default

    @staticmethod
    def bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (UUID, datetime, date)):
        return str(value)
    if isinstance(value, BaseModel):
        return json_safe(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "__table__"):
        result: dict[str, Any] = {}
        for column in value.__table__.columns:
            result[column.name] = json_safe(getattr(value, column.name))
        return result
    return str(value)
