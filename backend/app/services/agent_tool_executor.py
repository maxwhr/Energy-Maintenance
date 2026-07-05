from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AgentStep, AgentToolCall, User
from app.repositories.agent_repository import AgentRepository
from app.services.agent_tools import AGENT_TOOL_CLASSES, AgentToolExecutionContext, AgentToolResult


class AgentToolExecutorError(ValueError):
    pass


class AgentToolExecutor:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AgentRepository(db)

    def execute_tool(
        self,
        *,
        run_id: str,
        step: AgentStep,
        tool_name: str,
        payload: dict[str, Any],
        context: AgentToolExecutionContext,
        current_user: User,
    ) -> AgentToolResult:
        started = time.perf_counter()
        call = self.repository.create_tool_call(
            AgentToolCall(
                run_id=run_id,
                step_id=step.id,
                tool_name=tool_name,
                tool_version="v1",
                status="running",
                input_json=payload,
                output_json=None,
            )
        )
        self.db.commit()

        result: AgentToolResult
        try:
            result = self._execute_registered_tool(tool_name, payload, context, current_user=current_user)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            result = AgentToolResult(
                tool_name=tool_name,
                status="failed",
                summary=f"{tool_name} failed during execution.",
                error_code="tool_execution_error",
                error_message=str(exc),
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        persisted_call = self.db.get(AgentToolCall, call.id)
        if persisted_call:
            persisted_call.status = result.status
            persisted_call.output_json = result.to_output()
            persisted_call.latency_ms = latency_ms
            persisted_call.error_code = result.error_code
            persisted_call.error_message = result.error_message or result.blocked_reason
            self.repository.update_tool_call(persisted_call)

        step.status = result.status
        step.output_json = result.to_output()
        step.error_message = result.error_message or result.blocked_reason
        step.finished_at = datetime.now(timezone.utc)
        self.repository.update_step(step)
        self.db.commit()
        return result

    def _execute_registered_tool(
        self,
        tool_name: str,
        payload: dict[str, Any],
        context: AgentToolExecutionContext,
        *,
        current_user: User,
    ) -> AgentToolResult:
        registry_tool = self.repository.get_tool(tool_name)
        if not registry_tool:
            return AgentToolResult(
                tool_name=tool_name,
                status="blocked",
                summary="Agent tool is not registered.",
                blocked_reason="tool_not_registered",
            )
        allowed_roles = set(registry_tool.allowed_roles_json or [])
        if allowed_roles and current_user.role not in allowed_roles:
            return AgentToolResult(
                tool_name=tool_name,
                status="blocked",
                summary=f"Role {current_user.role} is not allowed to execute {tool_name}.",
                blocked_reason="role_not_allowed",
            )
        if not registry_tool.enabled and tool_name != "media_mimo_analysis":
            return AgentToolResult(
                tool_name=tool_name,
                status="blocked",
                summary=f"Agent tool {tool_name} is disabled.",
                blocked_reason="tool_disabled",
            )
        tool_class = AGENT_TOOL_CLASSES.get(tool_name)
        if not tool_class:
            return AgentToolResult(
                tool_name=tool_name,
                status="blocked",
                summary=f"No executor adapter is available for {tool_name}.",
                blocked_reason="executor_not_available",
            )
        tool = tool_class()
        result = tool.execute(payload, context)
        if registry_tool.requires_approval or registry_tool.risk_level == "high":
            result.requires_approval = True
            if result.status == "succeeded":
                result.status = "waiting_approval"
        return result


def parse_uuid_list(values: list[Any] | None) -> list[UUID]:
    result: list[UUID] = []
    for value in values or []:
        try:
            parsed = value if isinstance(value, UUID) else UUID(str(value))
        except (TypeError, ValueError):
            continue
        if parsed not in result:
            result.append(parsed)
    return result
