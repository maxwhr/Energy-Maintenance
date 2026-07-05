from __future__ import annotations

from typing import Any

from app.models import AgentArtifact, AgentRun, User
from app.schemas.agent import AgentRunCreateRequest, AgentRunRead
from app.services.agent_orchestrators.base import AgentOrchestratorError
from app.services.agent_orchestrators.workflow_base import WorkflowAgentOrchestrator
from app.services.agent_tools.base import AgentToolResult


class TaskOrchestrationOrchestrator(WorkflowAgentOrchestrator):
    DEFAULT_TOOLS = [
        "device_lookup",
        "device_history",
        "record_center_lookup",
        "task_draft_creator",
        "safety_guard",
        "human_approval",
    ]

    def create_run(self, payload: AgentRunCreateRequest, *, current_user: User) -> AgentRunRead:
        self.validate_creator(payload, current_user)
        if not payload.input_text and not payload.context.get("fault_description"):
            raise AgentOrchestratorError("task_orchestration_agent requires task or fault input_text")

        selected_tools = self.selected_tools(payload, self.DEFAULT_TOOLS)
        definition = self.require_definition_and_tools(payload.agent_code, selected_tools)
        run = self.create_agent_run(
            payload,
            current_user,
            mode="task_orchestration_draft",
            provider=definition.default_model_provider or "rule_based",
            model_name=definition.default_model_name or "task_orchestration_orchestrator_v1",
            selected_tools=selected_tools,
        )

        results: dict[str, AgentToolResult] = {}
        self._validate_step(run, payload, current_user, selected_tools)
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=2,
            step_name="load_device_context",
            tool_name="device_lookup",
            reasoning_summary="Load selected PV inverter context before drafting a maintenance task.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=3,
            step_name="load_recent_history",
            tool_name="device_history",
            reasoning_summary="Load recent device maintenance history and recurrence context.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=4,
            step_name="load_record_center_context",
            tool_name="record_center_lookup",
            reasoning_summary="Load cross-module record-center context for traceable draft creation.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=5,
            step_name="build_task_draft",
            tool_name="task_draft_creator",
            reasoning_summary="Create a draft-only task artifact payload; no formal maintenance_task row is created.",
        )
        safety_payload = {
            **self.build_tool_payload(payload, "safety_guard"),
            "task_draft": self.result_data(results, "task_draft_creator").get("task_draft"),
            "source": "task_orchestration_agent",
        }
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=6,
            step_name="build_safety_requirement",
            tool_name="safety_guard",
            reasoning_summary="Generate conservative safety notes for the task draft.",
            override_payload=safety_payload,
        )
        next_step_index = self._execute_extra_tools(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            start_index=7,
        )

        artifacts = self._create_task_artifacts(run, payload, current_user, results, step_index=next_step_index)
        approval = self.create_approval(
            run=run,
            approval_type="task_draft_review",
            requested_action="review_task_draft",
            payload_json={
                "artifact_types": [item.artifact_type for item in artifacts],
                "artifact_ids": [str(item.id) for item in artifacts],
                "draft_only": True,
                "formal_task_created": False,
            },
            current_user=current_user,
        )
        self.create_step(
            run_id=run.run_id,
            step_index=next_step_index + 1,
            step_type="approval",
            step_name="create_approval_request",
            status="waiting_approval",
            input_json={"approval_type": "task_draft_review"},
            output_json={"approval_id": str(approval.id), "status": approval.status, "formal_task_created": False},
            reasoning_summary="Create a human approval request for the task draft without creating a formal maintenance task.",
        )
        self.finalize(
            run=run,
            current_user=current_user,
            results=results,
            artifacts=artifacts,
            final_answer=self._final_answer(payload, results, artifacts),
            confidence=self._confidence(results),
            requires_approval=True,
            approval_status="pending",
            step_index=next_step_index + 2,
            step_name="finalize_task_agent_run",
        )
        return AgentRunRead.model_validate(run)

    def _validate_step(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        selected_tools: list[str],
    ) -> None:
        self.create_step(
            run_id=run.run_id,
            step_index=1,
            step_type="validation",
            step_name="validate_task_input",
            status="succeeded",
            input_json={
                "agent_code": payload.agent_code,
                "role": current_user.role,
                "device_id": str(payload.device_id) if payload.device_id else None,
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
            },
            output_json={
                "selected_tools": selected_tools,
                "draft_only": True,
                "formal_task_created": False,
                "external_api_called": False,
            },
            reasoning_summary="Task input and no-formal-write boundary were validated before draft generation.",
        )

    def _create_task_artifacts(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
        *,
        step_index: int,
    ) -> list[AgentArtifact]:
        task_data = self.result_data(results, "task_draft_creator")
        safety = self.result_data(results, "safety_guard")
        device = self.compact_device(self.result_data(results, "device_lookup"))
        record_center = self.result_data(results, "record_center_lookup")
        raw_draft = task_data.get("task_draft") if isinstance(task_data.get("task_draft"), dict) else {}
        draft = {
            "title": raw_draft.get("title") or self._default_title(payload),
            "device_id": str(run.device_id) if run.device_id else raw_draft.get("device_id"),
            "device": device,
            "manufacturer": payload.context.get("manufacturer") or raw_draft.get("manufacturer") or device.get("manufacturer"),
            "product_series": payload.context.get("product_series") or raw_draft.get("product_series") or device.get("product_series"),
            "fault_type": payload.context.get("fault_type") or raw_draft.get("fault_type") or "unknown",
            "alarm_code": payload.context.get("alarm_code") or raw_draft.get("alarm_code"),
            "priority": raw_draft.get("priority") or payload.context.get("priority") or "medium",
            "description": raw_draft.get("description") or raw_draft.get("fault_description") or payload.input_text or "",
            "suggested_assignee_id": raw_draft.get("suggested_assignee_id") or payload.context.get("suggested_assignee_id"),
            "suggested_due_time": raw_draft.get("suggested_due_time") or payload.context.get("suggested_due_time"),
            "safety_notes": safety.get("safety_notes") or raw_draft.get("safety_notes") or [],
            "source_agent_run_id": run.run_id,
            "source_artifact_ids": [],
            "record_center_context": {
                "total": record_center.get("total"),
                "items": (record_center.get("items") or [])[:5],
            },
            "requires_approval": True,
            "formal_task_created": False,
            "formal_task_id": None,
        }
        safety_checklist = {
            "must_do": safety.get("must_do") or [],
            "risk_level": safety.get("risk_level") or "medium",
            "warnings": safety.get("warnings") or [],
            "notices": safety.get("notices") or [],
            "safety_notes": safety.get("safety_notes") or [],
            "requires_field_engineer_confirmation": True,
        }
        task_artifact = self.create_artifact(
            run=run,
            artifact_type="task_draft",
            title="检修工单草稿",
            content_text="检修工单草稿已生成，需 expert/admin 审批；不会自动创建正式 maintenance_task。",
            content_json=draft,
        )
        draft["source_artifact_ids"] = [str(task_artifact.id)]
        task_artifact.content_json = draft
        self.repository.create_artifact(task_artifact)
        safety_artifact = self.create_artifact(
            run=run,
            artifact_type="safety_checklist",
            title="工单安全要求",
            content_text="工单安全要求已生成，现场分派和开工前必须人工确认。",
            content_json=safety_checklist,
        )
        artifacts = [task_artifact, safety_artifact]
        contribution = self.result_data(results, "knowledge_contribution_draft_creator").get(
            "knowledge_contribution_draft"
        )
        if isinstance(contribution, dict):
            artifacts.append(
                self.create_artifact(
                    run=run,
                    artifact_type="knowledge_contribution_draft",
                    title="知识贡献草稿",
                    content_text="知识贡献草稿由显式工具链生成，正式提交仍需人工审批。",
                    content_json=contribution,
                    source_type="agent_tool",
                    source_id="knowledge_contribution_draft_creator",
                )
            )
        correction = self.result_data(results, "correction_submitter").get("correction_draft")
        if isinstance(correction, dict):
            artifacts.append(
                self.create_artifact(
                    run=run,
                    artifact_type="correction_draft",
                    title="人工修正草稿",
                    content_text="人工修正草稿由显式工具链生成，正式提交仍需人工审批。",
                    content_json=correction,
                    source_type="agent_tool",
                    source_id="correction_submitter",
                )
            )
        trace_artifact = self.create_artifact(
            run=run,
            artifact_type="evidence_trace_summary",
            title="工单草稿证据追溯摘要",
            content_text="工单草稿证据追溯摘要已生成，可追踪设备、履历、记录中心、工具调用和审批草稿。",
            content_json=self.trace_summary(
                run=run,
                results=results,
                artifacts=artifacts,
                media_ids=payload.requested_media_ids(),
                extra={"formal_task_created": False},
            ),
        )
        artifacts.append(trace_artifact)
        self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="artifact_generation",
            step_name="create_task_artifact",
            status="succeeded",
            input_json={"tool_status_counts": self.status_counts(results.values())},
            output_json={
                "artifact_types": [item.artifact_type for item in artifacts],
                "requires_approval": True,
                "formal_task_created": False,
            },
            reasoning_summary="Create task draft, safety checklist, and trace artifacts without creating a formal maintenance task.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifacts_created",
            event_message="Task draft, safety checklist, and trace summary artifacts created",
            payload_json={"artifact_ids": [str(item.id) for item in artifacts], "formal_task_created": False},
            current_user=current_user,
        )
        return artifacts

    def _execute_extra_tools(
        self,
        *,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        selected_tools: list[str],
        results: dict[str, AgentToolResult],
        start_index: int,
    ) -> int:
        handled = {"device_lookup", "device_history", "record_center_lookup", "task_draft_creator", "safety_guard"}
        step_index = start_index
        for tool_name in selected_tools:
            if tool_name in handled or tool_name in results:
                continue
            self.execute_tool_step(
                run=run,
                payload=payload,
                current_user=current_user,
                selected_tools=selected_tools,
                results=results,
                step_index=step_index,
                step_name=tool_name,
                tool_name=tool_name,
                reasoning_summary=(
                    "Execute an explicitly requested compatibility tool through Agent Tool Executor; "
                    "formal writes remain draft-only and approval-gated."
                ),
            )
            step_index += 1
        return step_index

    @staticmethod
    def _default_title(payload: AgentRunCreateRequest) -> str:
        fault_type = payload.context.get("fault_type") or "光伏逆变器故障"
        alarm_code = payload.context.get("alarm_code")
        suffix = f" - {alarm_code}" if alarm_code else ""
        return f"{fault_type} 检修工单草稿{suffix}"

    @staticmethod
    def _confidence(results: dict[str, AgentToolResult]) -> float:
        succeeded = sum(1 for result in results.values() if result.status in {"succeeded", "waiting_approval"})
        blocked = sum(1 for result in results.values() if result.status == "blocked")
        return max(0.25, min(0.78, 0.34 + 0.06 * succeeded - 0.03 * blocked))

    def _final_answer(
        self,
        payload: AgentRunCreateRequest,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
    ) -> str:
        blocked = [name for name, result in results.items() if result.status == "blocked"]
        failed = [name for name, result in results.items() if result.status == "failed"]
        lines = [
            "工单编排智能体已生成检修工单草稿并创建人工审批记录。",
            f"输入摘要：{(payload.input_text or payload.context.get('fault_description') or '未提供')[:260]}",
            f"生成 artifact：{', '.join(item.artifact_type for item in artifacts)}。",
            f"Blocked 工具：{', '.join(blocked) if blocked else '无'}；Failed 工具：{', '.join(failed) if failed else '无'}。",
            "本次只生成 task_draft artifact 和 task_draft_review approval；没有创建正式 maintenance_task，没有自动分派、开工、完成或取消任务。",
            "本次未调用真实外部 API、云端模型、本地模型、OCR、embedding 或 pgvector。",
            "审批通过只改变 agent_approvals 状态；后续从草稿转正式工单必须另行执行人工确认流程。",
        ]
        return "\n".join(lines)
