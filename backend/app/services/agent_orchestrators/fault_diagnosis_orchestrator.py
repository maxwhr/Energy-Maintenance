from __future__ import annotations

from typing import Any

from app.models import AgentArtifact, AgentRun, User
from app.schemas.agent import AgentRunCreateRequest, AgentRunRead
from app.services.agent_orchestrators.base import AgentOrchestratorError
from app.services.agent_orchestrators.workflow_base import WorkflowAgentOrchestrator
from app.services.agent_tools.base import AgentToolResult


class FaultDiagnosisOrchestrator(WorkflowAgentOrchestrator):
    DEFAULT_TOOLS = [
        "device_lookup",
        "device_history",
        "media_lookup",
        "knowledge_search",
        "kg_business_context",
        "diagnosis_rule_engine",
        "safety_guard",
    ]

    def create_run(self, payload: AgentRunCreateRequest, *, current_user: User) -> AgentRunRead:
        self.validate_creator(payload, current_user)
        if not payload.input_text and not payload.context.get("fault_description"):
            raise AgentOrchestratorError("fault_diagnosis_agent requires fault symptom input_text")

        selected_tools = self.selected_tools(payload, self.DEFAULT_TOOLS)
        definition = self.require_definition_and_tools(payload.agent_code, selected_tools)
        run = self.create_agent_run(
            payload,
            current_user,
            mode="fault_diagnosis_orchestration",
            provider=definition.default_model_provider or "rule_based",
            model_name=definition.default_model_name or "fault_diagnosis_orchestrator_v1",
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
            reasoning_summary="Load PV inverter device context before diagnosis reasoning.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=3,
            step_name="load_device_history",
            tool_name="device_history",
            reasoning_summary="Load recent maintenance and recurrence context for the selected device.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=4,
            step_name="load_multimodal_evidence",
            tool_name="media_lookup",
            reasoning_summary="Load selected media metadata and multimodal evidence summaries when media is available.",
            optional=True,
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=5,
            step_name="retrieve_approved_knowledge",
            tool_name="knowledge_search",
            reasoning_summary="Retrieve parsed and approved PV inverter knowledge chunks with source references.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=6,
            step_name="query_knowledge_graph",
            tool_name="kg_business_context",
            reasoning_summary="Query in-database knowledge graph context; no-hit is treated as empty context.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=7,
            step_name="run_diagnosis_rules",
            tool_name="diagnosis_rule_engine",
            reasoning_summary="Run rule-based diagnosis service and persist diagnosis_records through the service layer.",
        )
        safety_payload = {
            **self.build_tool_payload(payload, "safety_guard"),
            "diagnosis_result": self.result_data(results, "diagnosis_rule_engine"),
            "knowledge_reference_count": len((self.result_data(results, "knowledge_search")).get("references") or []),
        }
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=8,
            step_name="run_safety_guard",
            tool_name="safety_guard",
            reasoning_summary="Produce conservative PV inverter electrical safety guardrails before any field action.",
            override_payload=safety_payload,
        )

        artifacts = self._build_artifacts(run, payload, current_user, results)
        final_answer = self._final_answer(payload, results, artifacts)
        confidence = self._summary_confidence(results)
        self.finalize(
            run=run,
            current_user=current_user,
            results=results,
            artifacts=artifacts,
            final_answer=final_answer,
            confidence=confidence,
            requires_approval=False,
            approval_status="not_required",
            step_index=11,
            step_name="finalize_diagnosis_agent_run",
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
            step_name="validate_diagnosis_input",
            status="succeeded",
            input_json={
                "agent_code": payload.agent_code,
                "role": current_user.role,
                "device_id": str(payload.device_id) if payload.device_id else None,
                "media_count": len(payload.requested_media_ids()),
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
            },
            output_json={
                "selected_tools": selected_tools,
                "fault_type": payload.context.get("fault_type"),
                "alarm_code": payload.context.get("alarm_code"),
                "external_api_called": False,
            },
            reasoning_summary="Diagnosis input, role, selected tools, and draft-only safety boundaries were validated.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="orchestration_step",
            event_message="validate_diagnosis_input completed",
            payload_json={"step": "validate_diagnosis_input", "status": "succeeded"},
            current_user=current_user,
        )

    def _build_artifacts(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
    ) -> list[AgentArtifact]:
        diagnosis = self.result_data(results, "diagnosis_rule_engine")
        knowledge = self.result_data(results, "knowledge_search")
        kg = self.result_data(results, "kg_business_context")
        safety = self.result_data(results, "safety_guard")
        media = self.result_data(results, "media_lookup")
        device = self.compact_device(self.result_data(results, "device_lookup"))
        summary = {
            "device_id": str(run.device_id) if run.device_id else None,
            "device": device,
            "manufacturer": payload.context.get("manufacturer") or diagnosis.get("manufacturer") or device.get("manufacturer"),
            "product_series": payload.context.get("product_series") or diagnosis.get("product_series") or device.get("product_series"),
            "fault_type": diagnosis.get("fault_type") or payload.context.get("fault_type") or "unknown",
            "alarm_code": diagnosis.get("alarm_code") or payload.context.get("alarm_code"),
            "symptom_summary": payload.input_text or payload.context.get("fault_description") or "",
            "diagnosis_trace_id": diagnosis.get("trace_id"),
            "possible_causes": diagnosis.get("possible_causes") or [],
            "inspection_steps": diagnosis.get("inspection_steps") or [],
            "knowledge_references": diagnosis.get("references") or knowledge.get("references") or [],
            "kg_context": self._kg_context(kg),
            "media_evidence_summary": {
                "items": media.get("items") or [],
                "multimodal_summaries": media.get("multimodal_summaries") or {},
            },
            "safety_risks": safety.get("warnings") or safety.get("safety_notes") or [],
            "recommended_actions": diagnosis.get("recommended_actions") or [],
            "confidence": diagnosis.get("confidence") or self._summary_confidence(results),
            "requires_human_review": True,
            "limitations": [
                "诊断建议不是最终维修结论，必须由现场工程师结合厂家手册复核。",
                "本次智能体编排不调用真实外部 API，不使用 embedding、pgvector 或云端模型。",
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
        diagnosis_artifact = self.create_artifact(
            run=run,
            artifact_type="diagnosis_summary",
            title="故障诊断摘要",
            content_text="故障诊断摘要已生成，结论仅供检修辅助，必须人工复核。",
            content_json=summary,
        )
        safety_artifact = self.create_artifact(
            run=run,
            artifact_type="safety_checklist",
            title="诊断安全复核清单",
            content_text="安全复核清单已生成，现场作业前必须断电、验电、绝缘防护和双人复核。",
            content_json=safety_checklist,
        )
        artifacts = [diagnosis_artifact, safety_artifact]
        self.create_step(
            run_id=run.run_id,
            step_index=9,
            step_type="artifact_generation",
            step_name="build_diagnosis_summary",
            status="succeeded",
            input_json={"tool_status_counts": self.status_counts(results.values())},
            output_json={
                "artifact_types": [item.artifact_type for item in artifacts],
                "diagnosis_trace_id": diagnosis.get("trace_id"),
                "requires_human_review": True,
            },
            reasoning_summary="Build a structured diagnosis artifact from device, history, media, knowledge, KG, rules, and safety outputs.",
        )
        trace = self.trace_summary(
            run=run,
            results=results,
            artifacts=artifacts,
            media_ids=payload.requested_media_ids(),
            extra={
                "diagnosis_trace_id": diagnosis.get("trace_id"),
                "knowledge_reference_count": len(summary["knowledge_references"]),
                "kg_hit_count": len(summary["kg_context"]),
            },
        )
        trace_artifact = self.create_artifact(
            run=run,
            artifact_type="evidence_trace_summary",
            title="诊断证据追溯摘要",
            content_text="诊断证据追溯摘要已生成，可追踪到工具调用、知识引用、媒体和诊断 trace_id。",
            content_json=trace,
        )
        artifacts.append(trace_artifact)
        self.create_step(
            run_id=run.run_id,
            step_index=10,
            step_type="evidence_linking",
            step_name="create_trace_links",
            status="succeeded",
            input_json={"artifact_types": [item.artifact_type for item in artifacts]},
            output_json=self.trace_summary(
                run=run,
                results=results,
                artifacts=artifacts,
                media_ids=payload.requested_media_ids(),
                extra={"trace_artifact_id": str(trace_artifact.id), "external_api_called": False},
            ),
            reasoning_summary="Create an auditable trace summary without fabricating external evidence links.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifacts_created",
            event_message="Diagnosis summary, safety checklist, and trace summary artifacts created",
            payload_json={"artifact_ids": [str(item.id) for item in artifacts]},
            current_user=current_user,
        )
        return artifacts

    @staticmethod
    def _kg_context(kg: dict[str, Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for key in ("related_causes", "inspection_items", "recommended_actions", "safety_risks", "evidence"):
            value = kg.get(key)
            if isinstance(value, list):
                result.extend(item for item in value[:5] if isinstance(item, dict))
        return result

    @staticmethod
    def _summary_confidence(results: dict[str, AgentToolResult]) -> float:
        diagnosis = WorkflowAgentOrchestrator.result_data(results, "diagnosis_rule_engine")
        if isinstance(diagnosis.get("confidence"), (int, float)):
            return float(diagnosis["confidence"])
        succeeded = sum(1 for result in results.values() if result.status in {"succeeded", "waiting_approval"})
        return min(0.78, 0.35 + 0.06 * succeeded)

    def _final_answer(
        self,
        payload: AgentRunCreateRequest,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
    ) -> str:
        blocked = [name for name, result in results.items() if result.status == "blocked"]
        failed = [name for name, result in results.items() if result.status == "failed"]
        mocked = [name for name, result in results.items() if self.is_mocked(result)]
        diagnosis = self.result_data(results, "diagnosis_rule_engine")
        references = diagnosis.get("references") or self.result_data(results, "knowledge_search").get("references") or []
        lines = [
            "故障诊断智能体已完成受控 dry-run 编排。",
            f"故障现象：{(payload.input_text or payload.context.get('fault_description') or '未提供')[:260]}",
            f"使用证据：设备信息、维修履历、媒体摘要、知识库引用 {len(references)} 条、知识图谱上下文和规则诊断结果。",
            f"生成 artifact：{', '.join(item.artifact_type for item in artifacts)}。",
            f"Blocked 工具：{', '.join(blocked) if blocked else '无'}；Failed 工具：{', '.join(failed) if failed else '无'}；Mocked 结果：{', '.join(mocked) if mocked else '无'}。",
            "诊断建议不是最终维修结论，不能替代现场工程师判断或华为/阳光电源厂家手册。",
            "本次未调用真实外部 API、云端模型、本地模型、OCR、embedding 或 pgvector。",
            "推荐下一步：由专家复核 diagnosis_summary 后，再创建 SOP 编排智能体和工单草稿编排智能体。",
        ]
        return "\n".join(lines)
