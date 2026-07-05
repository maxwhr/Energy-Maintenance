from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.models import AgentApproval, AgentArtifact, AgentRun, User
from app.schemas.agent import AgentRunCreateRequest
from app.services.agent_orchestrators.base import AgentOrchestratorError, BaseAgentOrchestrator
from app.services.agent_tool_executor import AgentToolExecutor
from app.services.agent_tool_registry import AgentToolRegistryService
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, json_safe


class WorkflowAgentOrchestrator(BaseAgentOrchestrator):
    """Shared helpers for draft-only business orchestration agents."""

    def __init__(self, db):
        super().__init__(db)
        self.registry = AgentToolRegistryService(db)
        self.executor = AgentToolExecutor(db)

    def validate_creator(self, payload: AgentRunCreateRequest, current_user: User) -> None:
        if current_user.role not in {"admin", "expert", "engineer"}:
            raise AgentOrchestratorError("viewer cannot create agent runs")
        if payload.mock_run and current_user.role not in {"admin", "expert"}:
            raise AgentOrchestratorError("mock-run is limited to admin and expert users")

    def selected_tools(self, payload: AgentRunCreateRequest, default_tools: list[str]) -> list[str]:
        return list(dict.fromkeys(payload.requested_tools() or default_tools))

    def require_definition_and_tools(self, agent_code: str, selected_tools: list[str]) -> Any:
        definition = self.registry.get_definition_model(agent_code)
        if not definition or not definition.enabled:
            raise AgentOrchestratorError("Agent definition is not available")
        tools = self.registry.get_tools_by_name(selected_tools)
        missing = sorted(set(selected_tools) - {tool.tool_name for tool in tools})
        if missing:
            raise AgentOrchestratorError(f"Agent tools not found: {', '.join(missing)}")
        return definition

    def create_agent_run(
        self,
        payload: AgentRunCreateRequest,
        current_user: User,
        *,
        mode: str,
        provider: str = "rule_based",
        model_name: str = "rule_based_orchestrator_v1",
        selected_tools: list[str],
    ) -> AgentRun:
        now = self.now()
        run = self.repository.create_run(
            AgentRun(
                run_id=f"agent-{uuid4().hex}",
                agent_code=payload.agent_code,
                user_id=current_user.id,
                device_id=payload.device_id,
                status="running",
                input_text=payload.input_text,
                input_media_ids_json=[str(item) for item in payload.requested_media_ids()],
                context_json={
                    **payload.context,
                    "mode": mode,
                    "dry_run": payload.dry_run,
                    "mock_run": payload.mock_run,
                    "requested_tools": selected_tools,
                    "tool_inputs": payload.tool_inputs,
                    "draft_only": True,
                    "external_api_called": False,
                },
                provider=provider,
                model_name=model_name,
                final_answer=None,
                confidence=Decimal("0.1000"),
                requires_human_approval=False,
                approval_status="not_required",
                started_at=now,
            )
        )
        self.db.commit()
        return run

    def execute_tool_step(
        self,
        *,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        selected_tools: list[str],
        results: dict[str, AgentToolResult],
        step_index: int,
        step_name: str,
        tool_name: str,
        reasoning_summary: str,
        override_payload: dict[str, Any] | None = None,
        optional: bool = False,
    ) -> AgentToolResult:
        if tool_name not in selected_tools:
            result = AgentToolResult(
                tool_name=tool_name,
                status="skipped",
                summary=f"{tool_name} was not selected for this agent run.",
            )
            self.create_step(
                run_id=run.run_id,
                step_index=step_index,
                step_type="tool_execution",
                step_name=step_name,
                status="skipped",
                input_json={"tool_name": tool_name},
                output_json=result.to_output(),
                reasoning_summary=f"{tool_name} was not selected for this agent run.",
            )
            results[tool_name] = result
            return result
        if optional and tool_name == "media_lookup" and not payload.requested_media_ids():
            result = AgentToolResult(
                tool_name=tool_name,
                status="skipped",
                summary="No media_ids were provided, so media evidence lookup was skipped.",
                data={"items": [], "multimodal_summaries": {}, "media_ids": []},
            )
            self.create_step(
                run_id=run.run_id,
                step_index=step_index,
                step_type="tool_execution",
                step_name=step_name,
                status="skipped",
                input_json={"tool_name": tool_name, "media_ids": []},
                output_json=result.to_output(),
                reasoning_summary="No media evidence was selected for this run.",
            )
            results[tool_name] = result
            return result

        media_ids = payload.requested_media_ids()
        step = self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="tool_execution",
            step_name=step_name,
            status="running",
            input_json={
                "tool_name": tool_name,
                "device_id": str(payload.device_id) if payload.device_id else None,
                "media_ids": [str(item) for item in media_ids],
            },
            reasoning_summary=reasoning_summary,
        )
        context = AgentToolExecutionContext(
            db=self.db,
            current_user=current_user,
            run_id=run.run_id,
            device_id=payload.device_id,
            media_ids=media_ids,
            dry_run=payload.dry_run,
            context={
                **payload.context,
                "agent_code": payload.agent_code,
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
            },
        )
        result = self.executor.execute_tool(
            run_id=run.run_id,
            step=step,
            tool_name=tool_name,
            payload=override_payload or self.build_tool_payload(payload, tool_name),
            context=context,
            current_user=current_user,
        )
        results[tool_name] = result
        self.create_event(
            run_id=run.run_id,
            event_type="tool_executed",
            event_message=f"{step_name} executed {tool_name} with status {result.status}",
            payload_json=result.to_output(),
            current_user=current_user,
        )
        return result

    def build_tool_payload(self, payload: AgentRunCreateRequest, tool_name: str) -> dict[str, Any]:
        specific = payload.tool_inputs.get(tool_name, {}) if payload.tool_inputs else {}
        text = specific.get("input_text") or payload.context.get("fault_description") or payload.input_text
        return {
            **payload.context,
            **specific,
            "input_text": text,
            "question": specific.get("question") or payload.context.get("question") or text,
            "query": specific.get("query") or payload.context.get("query") or text,
            "fault_description": specific.get("fault_description") or payload.context.get("fault_description") or text,
            "device_id": str(payload.device_id) if payload.device_id else None,
            "media_ids": [str(item) for item in payload.requested_media_ids()],
            "dry_run": payload.dry_run,
            "mock_run": payload.mock_run,
            "agent_code": payload.agent_code,
        }

    def create_artifact(
        self,
        *,
        run: AgentRun,
        artifact_type: str,
        title: str,
        content_text: str,
        content_json: dict[str, Any],
        source_type: str = "agent_run",
        source_id: str | None = None,
    ) -> AgentArtifact:
        artifact = self.repository.create_artifact(
            AgentArtifact(
                run_id=run.run_id,
                artifact_type=artifact_type,
                title=title,
                content_text=content_text,
                content_json=json_safe(content_json),
                source_type=source_type,
                source_id=source_id or run.run_id,
            )
        )
        self.db.commit()
        return artifact

    def create_approval(
        self,
        *,
        run: AgentRun,
        approval_type: str,
        requested_action: str,
        payload_json: dict[str, Any],
        current_user: User,
    ) -> AgentApproval:
        approval = self.repository.create_approval(
            AgentApproval(
                run_id=run.run_id,
                approval_type=approval_type,
                requested_action=requested_action,
                payload_json=json_safe(payload_json),
                status="pending",
                requested_by=current_user.id,
            )
        )
        self.db.commit()
        self.create_event(
            run_id=run.run_id,
            event_type="approval_created",
            event_message=f"{approval_type} approval request created",
            payload_json={"approval_id": str(approval.id), "requested_action": requested_action},
            current_user=current_user,
        )
        return approval

    def finalize(
        self,
        *,
        run: AgentRun,
        current_user: User,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
        final_answer: str,
        confidence: float,
        requires_approval: bool,
        approval_status: str = "not_required",
        step_index: int,
        step_name: str,
    ) -> None:
        run.status = "waiting_approval" if requires_approval else self.run_status(results)
        run.requires_human_approval = requires_approval
        run.approval_status = approval_status
        run.final_answer = final_answer
        run.confidence = Decimal(f"{max(0.10, min(confidence, 0.86)):.4f}")
        run.finished_at = None if run.status == "waiting_approval" else self.now()
        self.repository.update_run(run)
        self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="finalization",
            step_name=step_name,
            status=run.status,
            input_json={"tool_status_counts": self.status_counts(results.values())},
            output_json={
                "final_answer": final_answer,
                "status": run.status,
                "confidence": float(run.confidence),
                "artifact_types": [item.artifact_type for item in artifacts],
                "requires_approval": requires_approval,
                "external_api_called": False,
            },
            reasoning_summary="Finalize the business agent run with draft-only, approval, safety, and boundary statements.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="run_completed",
            event_message=f"{run.agent_code} orchestration completed",
            payload_json={
                "status": run.status,
                "tool_status_counts": self.status_counts(results.values()),
                "artifact_ids": [str(item.id) for item in artifacts],
                "requires_approval": requires_approval,
                "external_api_called": False,
            },
            current_user=current_user,
        )
        self.db.commit()

    @staticmethod
    def result_data(results: dict[str, AgentToolResult], tool_name: str) -> dict[str, Any]:
        result = results.get(tool_name)
        return (result.data if result else {}) or {}

    @staticmethod
    def status_counts(results: Any) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    @staticmethod
    def run_status(results: dict[str, AgentToolResult]) -> str:
        if not results:
            return "blocked"
        statuses = {result.status for result in results.values()}
        if statuses == {"failed"}:
            return "failed"
        if statuses.issubset({"blocked", "skipped"}):
            return "blocked"
        return "succeeded"

    @staticmethod
    def tool_warnings(results: dict[str, AgentToolResult]) -> list[str]:
        warnings: list[str] = []
        for name, result in results.items():
            if result.status in {"blocked", "failed", "skipped"}:
                reason = result.blocked_reason or result.error_message or result.summary
                warnings.append(f"{name}: {result.status}; {reason}")
        return warnings

    @staticmethod
    def compact_device(data: dict[str, Any]) -> dict[str, Any]:
        device = data.get("device")
        if isinstance(device, dict):
            return device
        items = data.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            return first if isinstance(first, dict) else {}
        return {}

    @staticmethod
    def trace_summary(
        *,
        run: AgentRun,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
        media_ids: list[UUID],
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "agent_run_id": run.run_id,
            "device_id": str(run.device_id) if run.device_id else None,
            "media_ids": [str(item) for item in media_ids],
            "tool_status_counts": WorkflowAgentOrchestrator.status_counts(results.values()),
            "tool_names": list(results.keys()),
            "artifact_ids": [str(item.id) for item in artifacts],
            "artifact_types": [item.artifact_type for item in artifacts],
            "blocked_tools": [name for name, result in results.items() if result.status == "blocked"],
            "failed_tools": [name for name, result in results.items() if result.status == "failed"],
            "mocked": any(WorkflowAgentOrchestrator.is_mocked(result) for result in results.values()),
            "external_api_called": False,
            **(extra or {}),
        }

    @staticmethod
    def is_mocked(result: AgentToolResult) -> bool:
        data = result.data or {}
        if data.get("mocked") is True or data.get("source") in {"mocked_ocr", "mocked_analysis"}:
            return True
        for key in ("ocr_context", "analyses"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and ((item.get("raw_response_json") or {}).get("mocked") is True):
                        return True
        return False
