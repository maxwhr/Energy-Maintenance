from __future__ import annotations

from typing import Any

from app.models import AgentArtifact, AgentRun, User
from app.schemas.agent import AgentRunCreateRequest, AgentRunRead
from app.services.agent_orchestrators.base import AgentOrchestratorError
from app.services.agent_orchestrators.workflow_base import WorkflowAgentOrchestrator
from app.services.agent_tools.base import AgentToolResult


class SopPlannerOrchestrator(WorkflowAgentOrchestrator):
    DEFAULT_TOOLS = ["device_lookup", "knowledge_search", "kg_business_context", "sop_generator", "safety_guard"]

    def create_run(self, payload: AgentRunCreateRequest, *, current_user: User) -> AgentRunRead:
        self.validate_creator(payload, current_user)
        if not payload.input_text and not payload.context.get("diagnosis_trace_id") and not payload.context.get("fault_type"):
            raise AgentOrchestratorError("sop_planner_agent requires fault input or diagnosis_trace_id")

        selected_tools = self.selected_tools(payload, self.DEFAULT_TOOLS)
        definition = self.require_definition_and_tools(payload.agent_code, selected_tools)
        run = self.create_agent_run(
            payload,
            current_user,
            mode="sop_planner_orchestration",
            provider=definition.default_model_provider or "rule_based",
            model_name=definition.default_model_name or "sop_planner_orchestrator_v1",
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
            reasoning_summary="Load PV inverter device context for SOP draft planning.",
        )
        self._load_diagnosis_context(run, payload, current_user)
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=4,
            step_name="retrieve_sop_related_knowledge",
            tool_name="knowledge_search",
            reasoning_summary="Retrieve SOP, manual, alarm-code, and fault-case references for the draft.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=5,
            step_name="query_sop_kg_context",
            tool_name="kg_business_context",
            reasoning_summary="Query knowledge graph context for SOP tools, steps, parts, risks, and related evidence.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=6,
            step_name="generate_sop_draft",
            tool_name="sop_generator",
            reasoning_summary="Generate a structured SOP draft through SOPService without creating SOP execution records.",
        )
        safety_payload = {
            **self.build_tool_payload(payload, "safety_guard"),
            "sop_result": self.result_data(results, "sop_generator"),
            "source": "sop_planner_agent",
        }
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=7,
            step_name="build_safety_checklist",
            tool_name="safety_guard",
            reasoning_summary="Build conservative safety requirements for the draft SOP.",
            override_payload=safety_payload,
        )

        artifacts = self._create_sop_artifacts(run, payload, current_user, results)
        approval = self.create_approval(
            run=run,
            approval_type="sop_draft_review",
            requested_action="review_sop_draft",
            payload_json={
                "artifact_types": [item.artifact_type for item in artifacts],
                "artifact_ids": [str(item.id) for item in artifacts],
                "draft_only": True,
                "formal_sop_execution_created": False,
            },
            current_user=current_user,
        )
        self.create_step(
            run_id=run.run_id,
            step_index=9,
            step_type="approval",
            step_name="create_approval_request",
            status="waiting_approval",
            input_json={"approval_type": "sop_draft_review"},
            output_json={"approval_id": str(approval.id), "status": approval.status},
            reasoning_summary="Create a human approval request for the SOP draft; no formal SOP execution is created.",
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
            step_index=10,
            step_name="finalize_sop_agent_run",
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
            step_name="validate_sop_input",
            status="succeeded",
            input_json={
                "agent_code": payload.agent_code,
                "role": current_user.role,
                "device_id": str(payload.device_id) if payload.device_id else None,
                "diagnosis_trace_id": payload.context.get("diagnosis_trace_id"),
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
            },
            output_json={"selected_tools": selected_tools, "draft_only": True, "external_api_called": False},
            reasoning_summary="SOP input and draft-only approval boundaries were validated before tool execution.",
        )

    def _load_diagnosis_context(self, run: AgentRun, payload: AgentRunCreateRequest, current_user: User) -> None:
        diagnosis_trace_id = payload.context.get("diagnosis_trace_id") or (
            payload.tool_inputs.get("sop_generator", {}).get("diagnosis_trace_id") if payload.tool_inputs else None
        )
        self.create_step(
            run_id=run.run_id,
            step_index=3,
            step_type="context_loading",
            step_name="load_diagnosis_context",
            status="succeeded" if diagnosis_trace_id else "skipped",
            input_json={"diagnosis_trace_id": diagnosis_trace_id},
            output_json={
                "diagnosis_trace_id": diagnosis_trace_id,
                "message": "SOPService will resolve diagnosis_trace_id when provided."
                if diagnosis_trace_id
                else "No diagnosis_trace_id was provided; SOP draft uses current fault input.",
            },
            reasoning_summary="Load diagnosis context by trace_id when available; otherwise continue from the current fault input.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="orchestration_step",
            event_message="load_diagnosis_context completed",
            payload_json={"diagnosis_trace_id": diagnosis_trace_id},
            current_user=current_user,
        )

    def _create_sop_artifacts(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
    ) -> list[AgentArtifact]:
        sop = self.result_data(results, "sop_generator")
        knowledge = self.result_data(results, "knowledge_search")
        kg = self.result_data(results, "kg_business_context")
        safety = self.result_data(results, "safety_guard")
        draft = {
            "title": sop.get("title") or "光伏逆变器检修 SOP 草稿",
            "device_id": str(run.device_id) if run.device_id else None,
            "manufacturer": payload.context.get("manufacturer") or sop.get("manufacturer"),
            "product_series": payload.context.get("product_series") or sop.get("product_series"),
            "fault_type": sop.get("fault_type") or payload.context.get("fault_type") or "unknown",
            "alarm_code": sop.get("alarm_code") or payload.context.get("alarm_code"),
            "preconditions": [
                "确认设备、厂家、产品系列和告警代码与现场一致。",
                "确认已完成停电、验电、放电和挂牌上锁。",
            ],
            "tools": sop.get("tools_required") or kg.get("tools") or [],
            "materials": sop.get("materials_required") or kg.get("parts") or [],
            "steps": sop.get("steps") or [],
            "safety_requirements": sop.get("safety_requirements") or safety.get("safety_notes") or [],
            "acceptance_criteria": [
                "告警消除或告警状态已明确归档。",
                "复测绝缘、电压、电流、通信和并网状态符合厂家手册要求。",
                "作业记录、证据附件和复核结论已归档。",
            ],
            "review_points": [
                "是否符合华为/阳光电源厂家手册。",
                "是否覆盖现场高风险安全项。",
                "是否需要备件、停机窗口或专家升级处理。",
            ],
            "source_references": sop.get("references") or knowledge.get("references") or [],
            "kg_context": self._kg_context(kg),
            "requires_approval": True,
            "formal_sop_execution_created": False,
            "limitations": [
                "本草稿不等于正式 SOP execution。",
                "审批通过仅表示草稿状态更新，不会自动执行现场作业。",
                *self.tool_warnings(results),
            ],
        }
        safety_checklist = {
            "must_do": safety.get("must_do") or [],
            "risk_level": safety.get("risk_level") or "medium",
            "warnings": safety.get("warnings") or [],
            "notices": safety.get("notices") or [],
            "safety_notes": safety.get("safety_notes") or [],
            "requires_field_engineer_confirmation": True,
        }
        sop_artifact = self.create_artifact(
            run=run,
            artifact_type="sop_draft",
            title="SOP 编排草稿",
            content_text="SOP 草稿已生成，需 expert/admin 审批；不会自动创建 SOP execution。",
            content_json=draft,
        )
        safety_artifact = self.create_artifact(
            run=run,
            artifact_type="safety_checklist",
            title="SOP 安全复核清单",
            content_text="SOP 安全复核清单已生成，现场执行前必须人工确认。",
            content_json=safety_checklist,
        )
        artifacts = [sop_artifact, safety_artifact]
        trace = self.trace_summary(
            run=run,
            results=results,
            artifacts=artifacts,
            media_ids=payload.requested_media_ids(),
            extra={
                "source_reference_count": len(draft["source_references"]),
                "formal_sop_execution_created": False,
            },
        )
        trace_artifact = self.create_artifact(
            run=run,
            artifact_type="evidence_trace_summary",
            title="SOP 证据追溯摘要",
            content_text="SOP 证据追溯摘要已生成，可追踪知识引用、图谱上下文、工具调用和审批草稿。",
            content_json=trace,
        )
        artifacts.append(trace_artifact)
        self.create_step(
            run_id=run.run_id,
            step_index=8,
            step_type="artifact_generation",
            step_name="create_sop_artifact",
            status="succeeded",
            input_json={"tool_status_counts": self.status_counts(results.values())},
            output_json={"artifact_types": [item.artifact_type for item in artifacts], "requires_approval": True},
            reasoning_summary="Create SOP draft, safety checklist, and trace artifacts without formal SOP execution.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifacts_created",
            event_message="SOP draft, safety checklist, and trace summary artifacts created",
            payload_json={"artifact_ids": [str(item.id) for item in artifacts]},
            current_user=current_user,
        )
        return artifacts

    @staticmethod
    def _kg_context(kg: dict[str, Any]) -> dict[str, Any]:
        return {
            "tools": kg.get("tools") or [],
            "parts": kg.get("parts") or [],
            "safety_risks": kg.get("safety_risks") or [],
            "steps": [*(kg.get("inspection_items") or [])[:5], *(kg.get("recommended_actions") or [])[:5]],
            "evidence": kg.get("evidence") or [],
            "summary": kg.get("summary") or {},
        }

    @staticmethod
    def _confidence(results: dict[str, AgentToolResult]) -> float:
        sop = WorkflowAgentOrchestrator.result_data(results, "sop_generator")
        if isinstance(sop.get("confidence"), (int, float)):
            return float(sop["confidence"])
        succeeded = sum(1 for result in results.values() if result.status in {"succeeded", "waiting_approval"})
        return min(0.80, 0.36 + 0.06 * succeeded)

    def _final_answer(
        self,
        payload: AgentRunCreateRequest,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
    ) -> str:
        blocked = [name for name, result in results.items() if result.status == "blocked"]
        failed = [name for name, result in results.items() if result.status == "failed"]
        lines = [
            "SOP 编排智能体已生成草稿并创建人工审批记录。",
            f"输入摘要：{(payload.input_text or payload.context.get('diagnosis_trace_id') or '未提供')[:260]}",
            f"生成 artifact：{', '.join(item.artifact_type for item in artifacts)}。",
            f"Blocked 工具：{', '.join(blocked) if blocked else '无'}；Failed 工具：{', '.join(failed) if failed else '无'}。",
            "本次只生成 SOP 草稿 artifact 和 sop_draft_review approval，不创建正式 SOP execution，不修改正式 SOP 模板。",
            "本次未调用真实外部 API、云端模型、本地模型、OCR、embedding 或 pgvector。",
            "审批通过只改变 agent_approvals 状态；后续转正式 SOP/作业执行必须另行设计人工确认流程。",
        ]
        return "\n".join(lines)
