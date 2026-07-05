from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import AgentApproval, AgentArtifact, AgentEventLog, AgentRun, AgentStep, User
from app.repositories.agent_repository import AgentRepository
from app.schemas.agent import (
    AgentApprovalRead,
    AgentArtifactRead,
    AgentEventLogRead,
    AgentRunCreateRequest,
    AgentRunDetail,
    AgentRunRead,
    AgentStepRead,
    AgentToolCallRead,
    AgentToolExecuteRequest,
    AgentToolExecuteResponse,
)
from app.services.agent_tool_executor import AgentToolExecutor, parse_uuid_list
from app.services.agent_tool_registry import AgentToolRegistryService
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, json_safe


class AgentRuntimeServiceError(ValueError):
    pass


class AgentRuntimePermissionError(PermissionError):
    pass


class AgentRuntimeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AgentRepository(db)
        self.registry = AgentToolRegistryService(db)

    def create_run(self, payload: AgentRunCreateRequest, *, current_user: User) -> AgentRunRead:
        if current_user.role not in {"admin", "expert", "engineer"}:
            raise AgentRuntimePermissionError("viewer cannot create agent runs")
        orchestrator_map = {
            "multimodal_evidence_agent": (
                "MultimodalEvidenceAgentOrchestrator",
                "app.services.agent_orchestrators.multimodal_evidence_orchestrator",
            ),
            "fault_diagnosis_agent": (
                "FaultDiagnosisOrchestrator",
                "app.services.agent_orchestrators.fault_diagnosis_orchestrator",
            ),
            "sop_planner_agent": (
                "SopPlannerOrchestrator",
                "app.services.agent_orchestrators.sop_planner_orchestrator",
            ),
            "task_orchestration_agent": (
                "TaskOrchestrationOrchestrator",
                "app.services.agent_orchestrators.task_orchestration_orchestrator",
            ),
            "knowledge_curator_agent": (
                "KnowledgeCuratorOrchestrator",
                "app.services.agent_orchestrators.knowledge_curator_orchestrator",
            ),
        }
        if payload.agent_code in orchestrator_map:
            if payload.mock_run and current_user.role not in {"admin", "expert"}:
                raise AgentRuntimePermissionError("mock-run is limited to admin and expert users")
            import importlib

            from app.services.agent_orchestrators.base import AgentOrchestratorError

            try:
                class_name, module_name = orchestrator_map[payload.agent_code]
                orchestrator_class = getattr(importlib.import_module(module_name), class_name)
                return orchestrator_class(self.db).create_run(payload, current_user=current_user)
            except AgentOrchestratorError as exc:
                raise AgentRuntimeServiceError(str(exc)) from exc
        if payload.mock_run and current_user.role not in {"admin", "expert"}:
            raise AgentRuntimePermissionError("mock-run is limited to admin and expert users")
        definition = self.registry.get_definition_model(payload.agent_code)
        if not definition or not definition.enabled:
            raise AgentRuntimeServiceError("Agent definition not found or disabled")

        tool_names = payload.requested_tools() or (definition.tool_policy_json or {}).get("default_tools", [])
        tools = self.registry.get_tools_by_name(tool_names)
        missing = sorted(set(tool_names) - {tool.tool_name for tool in tools})
        if missing:
            raise AgentRuntimeServiceError(f"Agent tools not found: {', '.join(missing)}")

        media_ids = payload.requested_media_ids()
        now = datetime.now(timezone.utc)
        run = self.repository.create_run(
            AgentRun(
                run_id=f"agent-{uuid4().hex}",
                agent_code=payload.agent_code,
                user_id=current_user.id,
                device_id=payload.device_id,
                status="running",
                input_text=payload.input_text,
                input_media_ids_json=[str(media_id) for media_id in media_ids],
                context_json={
                    **payload.context,
                    "mode": "business_tool_execution",
                    "dry_run": payload.dry_run,
                    "mock_run": payload.mock_run,
                    "requested_tools": tool_names,
                    "tool_inputs": payload.tool_inputs,
                },
                provider=definition.default_model_provider or "rule_based",
                model_name=definition.default_model_name or "rule_based_demo_agent_v1",
                final_answer=None,
                confidence=Decimal("0.1000"),
                requires_human_approval=False,
                approval_status="not_required",
                started_at=now,
                finished_at=None,
            )
        )
        self.repository.create_step(
            AgentStep(
                run_id=run.run_id,
                step_index=1,
                step_type="planning",
                step_name="business_tool_plan",
                status="succeeded",
                input_json={"agent_code": payload.agent_code, "input_text": payload.input_text},
                output_json={"tool_names": tool_names, "dry_run": payload.dry_run, "external_model_called": False},
                reasoning_summary="Business tools are executed through registered service adapters.",
                started_at=now,
                finished_at=now,
            )
        )
        self.db.commit()

        executor = AgentToolExecutor(self.db)
        execution_context = AgentToolExecutionContext(
            db=self.db,
            current_user=current_user,
            run_id=run.run_id,
            device_id=payload.device_id,
            media_ids=media_ids,
            dry_run=payload.dry_run,
            context={**payload.context, "mock_run": payload.mock_run},
        )
        results: list[AgentToolResult] = []
        for step_index, tool_name in enumerate(tool_names, start=2):
            step = self.repository.create_step(
                AgentStep(
                    run_id=run.run_id,
                    step_index=step_index,
                    step_type="tool_execution",
                    step_name=tool_name,
                    status="running",
                    input_json={"tool_name": tool_name},
                    reasoning_summary="Executing registered business tool adapter.",
                    started_at=datetime.now(timezone.utc),
                )
            )
            self.db.commit()
            result = executor.execute_tool(
                run_id=run.run_id,
                step=step,
                tool_name=tool_name,
                payload=self._build_tool_payload(payload, tool_name, media_ids),
                context=execution_context,
                current_user=current_user,
            )
            results.append(result)
            self._create_artifacts_for_result(run, result)
            self.repository.create_event(
                AgentEventLog(
                    run_id=run.run_id,
                    event_type="tool_executed",
                    event_message=f"Tool {tool_name} finished with status {result.status}",
                    payload_json=result.to_output(),
                    created_by=current_user.id,
                )
            )
            self.db.commit()

        requires_approval = payload.requires_approval or any(result.requires_approval for result in results)
        run.status = self._status_from_results(results, requires_approval=requires_approval)
        run.requires_human_approval = requires_approval
        run.approval_status = "pending" if requires_approval else "not_required"
        run.final_answer = self._build_final_answer_from_results(definition.agent_name, payload, results)
        run.confidence = self._confidence_from_results(results)
        run.finished_at = None if run.status == "waiting_approval" else datetime.now(timezone.utc)
        self.repository.update_run(run)

        if requires_approval:
            self.repository.create_approval(
                AgentApproval(
                    run_id=run.run_id,
                    approval_type="human_review",
                    requested_action="approve_agent_tool_drafts",
                    payload_json={
                        "agent_code": payload.agent_code,
                        "tool_names": tool_names,
                        "dry_run": payload.dry_run,
                        "draft_only": True,
                        "tool_results": [result.to_output() for result in results if result.requires_approval],
                    },
                    status="pending",
                    requested_by=current_user.id,
                )
            )

        self.repository.create_artifact(
            AgentArtifact(
                run_id=run.run_id,
                artifact_type=self._artifact_type(definition.agent_type),
                title=f"{definition.agent_name} execution summary",
                content_text=run.final_answer,
                content_json={
                    "agent_code": payload.agent_code,
                    "tool_names": tool_names,
                    "requires_human_approval": requires_approval,
                    "external_api_called": False,
                    "mode": "business_tool_execution",
                    "tool_results": [result.to_output() for result in results],
                },
                source_type="agent_run",
                source_id=run.run_id,
            )
        )
        self.repository.create_event(
            AgentEventLog(
                run_id=run.run_id,
                event_type="run_completed",
                event_message="Agent run completed business tool orchestration",
                payload_json={
                    "agent_code": payload.agent_code,
                    "status": run.status,
                    "requires_human_approval": requires_approval,
                    "tool_status_counts": self._tool_status_counts(results),
                },
                created_by=current_user.id,
            )
        )
        self.db.commit()
        return AgentRunRead.model_validate(run)

    def execute_tool_for_run(
        self,
        run_id: str,
        payload: AgentToolExecuteRequest,
        *,
        current_user: User,
    ) -> AgentToolExecuteResponse:
        run = self._get_allowed_run(run_id, current_user=current_user)
        if current_user.role not in {"admin", "expert", "engineer"}:
            raise AgentRuntimePermissionError("viewer cannot execute agent tools")
        step_index = len(self.repository.list_steps(run_id)) + 1
        step = self.repository.create_step(
            AgentStep(
                run_id=run.run_id,
                step_index=step_index,
                step_type="manual_tool_execution",
                step_name=payload.tool_name,
                status="running",
                input_json={"tool_name": payload.tool_name},
                reasoning_summary="Manual agent tool execution endpoint.",
                started_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()
        context_json = run.context_json or {}
        media_ids = parse_uuid_list(run.input_media_ids_json or [])
        execution_context = AgentToolExecutionContext(
            db=self.db,
            current_user=current_user,
            run_id=run.run_id,
            device_id=run.device_id,
            media_ids=media_ids,
            dry_run=payload.dry_run,
            context=context_json,
        )
        tool_payload = {
            **context_json,
            **payload.input,
            "input_text": run.input_text,
            "device_id": str(run.device_id) if run.device_id else None,
            "media_ids": [str(media_id) for media_id in media_ids],
            "dry_run": payload.dry_run,
        }
        result = AgentToolExecutor(self.db).execute_tool(
            run_id=run.run_id,
            step=step,
            tool_name=payload.tool_name,
            payload=tool_payload,
            context=execution_context,
            current_user=current_user,
        )
        self._create_artifacts_for_result(run, result)
        if result.requires_approval:
            run.requires_human_approval = True
            run.approval_status = "pending"
            run.status = "waiting_approval"
            self.repository.update_run(run)
            self.repository.create_approval(
                AgentApproval(
                    run_id=run.run_id,
                    approval_type="human_review",
                    requested_action="approve_manual_agent_tool_draft",
                    payload_json={"tool_name": payload.tool_name, "tool_result": result.to_output(), "draft_only": True},
                    status="pending",
                    requested_by=current_user.id,
                )
            )
        self.repository.create_event(
            AgentEventLog(
                run_id=run.run_id,
                event_type="manual_tool_executed",
                event_message=f"Manual tool {payload.tool_name} finished with status {result.status}",
                payload_json=result.to_output(),
                created_by=current_user.id,
            )
        )
        self.db.commit()
        return AgentToolExecuteResponse(**result.to_output())

    def list_runs(
        self,
        *,
        current_user: User,
        status: str | None = None,
        agent_code: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        include_all = current_user.role in {"admin", "expert"}
        runs, total = self.repository.list_runs(
            current_user_id=current_user.id,
            include_all=include_all,
            status=status,
            agent_code=agent_code,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [AgentRunRead.model_validate(item).model_dump(mode="json") for item in runs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_run_detail(self, run_id: str, *, current_user: User) -> AgentRunDetail:
        run = self._get_allowed_run(run_id, current_user=current_user)
        return AgentRunDetail(
            run=AgentRunRead.model_validate(run),
            steps=[AgentStepRead.model_validate(item) for item in self.repository.list_steps(run_id)],
            tool_calls=[AgentToolCallRead.model_validate(item) for item in self.repository.list_tool_calls(run_id)],
            approvals=[AgentApprovalRead.model_validate(item) for item in self.repository.list_approvals(run_id)],
            artifacts=[AgentArtifactRead.model_validate(item) for item in self.repository.list_artifacts(run_id)],
        )

    def get_run_timeline(self, run_id: str, *, current_user: User) -> dict:
        detail = self.get_run_detail(run_id, current_user=current_user)
        events, total = self.repository.list_events(
            run_id=run_id,
            current_user_id=current_user.id,
            include_all=current_user.role in {"admin", "expert"} or True,
            page=1,
            page_size=100,
        )
        return {
            **detail.model_dump(mode="json"),
            "events": [AgentEventLogRead.model_validate(item).model_dump(mode="json") for item in events],
            "event_total": total,
        }

    def cancel_run(self, run_id: str, *, current_user: User) -> AgentRunRead:
        run = self._get_allowed_run(run_id, current_user=current_user)
        if run.status in {"succeeded", "failed", "cancelled", "blocked"}:
            raise AgentRuntimeServiceError("Only active or waiting runs can be cancelled")
        run.status = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        self.repository.update_run(run)
        self.repository.create_event(
            AgentEventLog(
                run_id=run.run_id,
                event_type="run_cancelled",
                event_message="Agent run cancelled",
                payload_json={"status": run.status},
                created_by=current_user.id,
            )
        )
        self.db.commit()
        return AgentRunRead.model_validate(run)

    def list_steps(self, run_id: str, *, current_user: User) -> list[AgentStepRead]:
        self._get_allowed_run(run_id, current_user=current_user)
        return [AgentStepRead.model_validate(item) for item in self.repository.list_steps(run_id)]

    def list_tool_calls(self, run_id: str, *, current_user: User) -> list[AgentToolCallRead]:
        self._get_allowed_run(run_id, current_user=current_user)
        return [AgentToolCallRead.model_validate(item) for item in self.repository.list_tool_calls(run_id)]

    def list_approvals(self, run_id: str, *, current_user: User) -> list[AgentApprovalRead]:
        self._get_allowed_run(run_id, current_user=current_user)
        return [AgentApprovalRead.model_validate(item) for item in self.repository.list_approvals(run_id)]

    def list_artifacts(self, run_id: str, *, current_user: User) -> list[AgentArtifactRead]:
        self._get_allowed_run(run_id, current_user=current_user)
        return [AgentArtifactRead.model_validate(item) for item in self.repository.list_artifacts(run_id)]

    def list_events(
        self,
        *,
        current_user: User,
        run_id: str | None = None,
        event_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        self._validate_page(page, page_size)
        include_all = current_user.role in {"admin", "expert"}
        events, total = self.repository.list_events(
            run_id=run_id,
            event_type=event_type,
            current_user_id=current_user.id,
            include_all=include_all,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [AgentEventLogRead.model_validate(item).model_dump(mode="json") for item in events],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def _get_allowed_run(self, run_id: str, *, current_user: User) -> AgentRun:
        run = self.repository.get_run(run_id)
        if not run:
            raise AgentRuntimeServiceError("Agent run not found")
        if current_user.role in {"admin", "expert"} or run.user_id == current_user.id:
            return run
        raise AgentRuntimePermissionError("Current user cannot access this agent run")

    @staticmethod
    def _build_tool_payload(payload: AgentRunCreateRequest, tool_name: str, media_ids: list) -> dict[str, Any]:
        specific = payload.tool_inputs.get(tool_name, {}) if payload.tool_inputs else {}
        return {
            **payload.context,
            **specific,
            "input_text": payload.input_text,
            "query": specific.get("query") or payload.context.get("query") or payload.input_text,
            "question": specific.get("question") or payload.context.get("question") or payload.input_text,
            "device_id": str(payload.device_id) if payload.device_id else None,
            "media_ids": [str(media_id) for media_id in media_ids],
            "dry_run": payload.dry_run,
            "mock_run": payload.mock_run,
        }

    def _create_artifacts_for_result(self, run: AgentRun, result: AgentToolResult) -> None:
        artifact_map = {
            "task_draft": "task_draft",
            "knowledge_contribution_draft": "knowledge_contribution_draft",
            "correction_draft": "correction_draft",
        }
        for key, artifact_type in artifact_map.items():
            if key not in result.data:
                continue
            self.repository.create_artifact(
                AgentArtifact(
                    run_id=run.run_id,
                    artifact_type=artifact_type,
                    title=f"{result.tool_name} {artifact_type}",
                    content_text=result.summary,
                    content_json=json_safe(result.data[key]),
                    source_type="agent_tool",
                    source_id=result.tool_name,
                )
            )

    @staticmethod
    def _status_from_results(results: list[AgentToolResult], *, requires_approval: bool) -> str:
        if requires_approval:
            return "waiting_approval"
        if not results:
            return "blocked"
        statuses = {result.status for result in results}
        if statuses == {"failed"}:
            return "failed"
        if statuses.issubset({"blocked", "skipped"}):
            return "blocked"
        return "succeeded"

    @staticmethod
    def _tool_status_counts(results: list[AgentToolResult]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    @staticmethod
    def _confidence_from_results(results: list[AgentToolResult]) -> Decimal:
        if not results:
            return Decimal("0.1000")
        succeeded = sum(1 for result in results if result.status == "succeeded")
        blocked = sum(1 for result in results if result.status == "blocked")
        failed = sum(1 for result in results if result.status == "failed")
        score = 0.35 + 0.35 * (succeeded / len(results)) - 0.08 * failed - 0.03 * blocked
        score = max(0.15, min(0.82, score))
        return Decimal(f"{score:.4f}")

    @staticmethod
    def _build_final_answer_from_results(
        agent_name: str,
        payload: AgentRunCreateRequest,
        results: list[AgentToolResult],
    ) -> str:
        status_counts: dict[str, int] = {}
        for result in results:
            status_counts[result.status] = status_counts.get(result.status, 0) + 1
        lines = [
            f"{agent_name} finished business tool orchestration.",
            f"Input: {(payload.input_text or 'not provided')[:240]}",
            f"Tool status counts: {status_counts}",
            "No external cloud model, local GGUF model, OCR runtime, embedding, pgvector, or Docker path was invoked.",
        ]
        for result in results:
            lines.append(f"- {result.tool_name}: {result.status}; {result.summary}")
        if any(result.requires_approval for result in results):
            lines.append("High-risk draft actions require human approval before any formal write action.")
        return "\n".join(lines)

    @staticmethod
    def _artifact_type(agent_type: str) -> str:
        mapping = {
            "multimodal_evidence": "multimodal_evidence_summary",
            "fault_diagnosis": "diagnosis_summary",
            "sop_planner": "sop_draft",
            "task_orchestration": "task_draft",
            "knowledge_curator": "knowledge_contribution_draft",
            "safety_guard": "safety_checklist",
        }
        return mapping.get(agent_type, "general")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise AgentRuntimeServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise AgentRuntimeServiceError("page_size must be between 1 and 100")
