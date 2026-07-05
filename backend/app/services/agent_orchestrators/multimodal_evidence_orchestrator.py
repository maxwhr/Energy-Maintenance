from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import AgentApproval, AgentArtifact, AgentRun, User
from app.schemas.agent import AgentRunCreateRequest, AgentRunRead
from app.schemas.multimodal_evidence import MediaEvidenceLinkCreate
from app.services.agent_orchestrators.base import AgentOrchestratorError, BaseAgentOrchestrator
from app.services.agent_tool_executor import AgentToolExecutor
from app.services.agent_tool_registry import AgentToolRegistryService
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, json_safe
from app.services.multimodal_evidence_service import (
    MultimodalEvidenceService,
    MultimodalEvidenceServiceError,
)


class MultimodalEvidenceAgentOrchestrator(BaseAgentOrchestrator):
    DEFAULT_TOOLS = ["media_lookup", "media_ocr", "media_mimo_analysis", "safety_guard"]
    INTERNAL_TOOLS = {"evidence_link"}

    def __init__(self, db: Session):
        super().__init__(db)
        self.registry = AgentToolRegistryService(db)
        self.executor = AgentToolExecutor(db)

    def create_run(self, payload: AgentRunCreateRequest, *, current_user: User) -> AgentRunRead:
        if current_user.role not in {"admin", "expert", "engineer"}:
            raise AgentOrchestratorError("viewer cannot create multimodal evidence agent runs")
        if payload.mock_run and current_user.role not in {"admin", "expert"}:
            raise AgentOrchestratorError("mock-run is limited to admin and expert users")

        definition = self.registry.get_definition_model(payload.agent_code)
        if not definition or not definition.enabled:
            raise AgentOrchestratorError("Multimodal evidence agent definition is not available")

        media_ids = payload.requested_media_ids()
        if not media_ids:
            raise AgentOrchestratorError("At least one media_id is required for multimodal evidence agent runs")

        selected_tools = payload.requested_tools() or self.DEFAULT_TOOLS
        selected_tools = list(dict.fromkeys(selected_tools))
        registered_tools = self.registry.get_tools_by_name(
            [tool for tool in selected_tools if tool not in self.INTERNAL_TOOLS]
        )
        missing = sorted(set(selected_tools) - {tool.tool_name for tool in registered_tools} - self.INTERNAL_TOOLS)
        if missing:
            raise AgentOrchestratorError(f"Agent tools not found: {', '.join(missing)}")

        now = self.now()
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
                    "mode": "multimodal_evidence_orchestration",
                    "dry_run": payload.dry_run,
                    "mock_run": payload.mock_run,
                    "requested_tools": selected_tools,
                    "tool_inputs": payload.tool_inputs,
                    "machine_evidence_boundary": (
                        "OCR and visual analysis are auxiliary evidence only and require human review."
                    ),
                },
                provider=definition.default_model_provider or "provider_gateway",
                model_name=definition.default_model_name or "multimodal_evidence_orchestrator_v1",
                final_answer=None,
                confidence=Decimal("0.1000"),
                requires_human_approval=False,
                approval_status="not_required",
                started_at=now,
            )
        )
        self.db.commit()

        results: dict[str, AgentToolResult] = {}
        self._step_validate_input(run, payload, current_user, media_ids, selected_tools)
        results["media_lookup"] = self._tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            media_ids=media_ids,
            selected_tools=selected_tools,
            step_index=2,
            step_name="load_media_context",
            tool_name="media_lookup",
            reasoning_summary="Load selected media metadata and existing multimodal evidence summary.",
        )
        results["media_ocr"] = self._tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            media_ids=media_ids,
            selected_tools=selected_tools,
            step_index=3,
            step_name="run_ocr_evidence",
            tool_name="media_ocr",
            reasoning_summary="Read existing OCR result or create a blocked/mock OCR evidence job without real OCR calls.",
        )
        results["media_mimo_analysis"] = self._tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            media_ids=media_ids,
            selected_tools=selected_tools,
            step_index=4,
            step_name="run_visual_analysis",
            tool_name="media_mimo_analysis",
            reasoning_summary="Read accepted/mocked visual analysis or create a blocked/mock provider-gateway result.",
        )
        safety_payload = {
            **payload.context,
            "input_text": payload.input_text,
            "fault_type": payload.context.get("fault_type"),
            "alarm_code": payload.context.get("alarm_code"),
            "media_analysis_summary": self._compact_tool_data(results.get("media_mimo_analysis")),
            "ocr_summary": self._compact_tool_data(results.get("media_ocr")),
        }
        results["safety_guard"] = self._tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            media_ids=media_ids,
            selected_tools=selected_tools,
            step_index=5,
            step_name="run_safety_guard",
            tool_name="safety_guard",
            reasoning_summary="Generate conservative PV inverter electrical safety checklist from input and evidence context.",
            override_payload=safety_payload,
        )

        artifacts = self._step_build_evidence_summary(run, payload, current_user, media_ids, results)
        evidence_link_ids = self._step_create_evidence_links(run, current_user, media_ids, artifacts, results)
        self._step_finalize_run(run, payload, current_user, results, artifacts, evidence_link_ids)
        return AgentRunRead.model_validate(run)

    def _step_validate_input(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        media_ids: list[UUID],
        selected_tools: list[str],
    ) -> None:
        self.create_step(
            run_id=run.run_id,
            step_index=1,
            step_type="validation",
            step_name="validate_input",
            status="succeeded",
            input_json={
                "agent_code": payload.agent_code,
                "media_ids": [str(item) for item in media_ids],
                "role": current_user.role,
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
            },
            output_json={
                "selected_tools": selected_tools,
                "media_count": len(media_ids),
                "external_api_called": False,
                "mock_run_allowed": current_user.role in {"admin", "expert"},
            },
            reasoning_summary="Input, role, media_ids, and requested tool chain were validated before execution.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="orchestration_step",
            event_message="validate_input completed",
            payload_json={"step": "validate_input", "status": "succeeded"},
            current_user=current_user,
        )

    def _tool_step(
        self,
        *,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        media_ids: list[UUID],
        selected_tools: list[str],
        step_index: int,
        step_name: str,
        tool_name: str,
        reasoning_summary: str,
        override_payload: dict[str, Any] | None = None,
    ) -> AgentToolResult:
        if tool_name not in selected_tools:
            self.create_step(
                run_id=run.run_id,
                step_index=step_index,
                step_type="tool_execution",
                step_name=step_name,
                status="skipped",
                input_json={"tool_name": tool_name},
                output_json={"tool_name": tool_name, "status": "skipped"},
                reasoning_summary=f"{tool_name} was not selected for this agent run.",
            )
            return AgentToolResult(tool_name=tool_name, status="skipped", summary=f"{tool_name} was skipped.")

        step = self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="tool_execution",
            step_name=step_name,
            status="running",
            input_json={"tool_name": tool_name, "media_ids": [str(item) for item in media_ids]},
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
        tool_payload = override_payload or self._build_tool_payload(payload, tool_name, media_ids)
        result = self.executor.execute_tool(
            run_id=run.run_id,
            step=step,
            tool_name=tool_name,
            payload=tool_payload,
            context=context,
            current_user=current_user,
        )
        self.create_event(
            run_id=run.run_id,
            event_type="tool_executed",
            event_message=f"{step_name} executed {tool_name} with status {result.status}",
            payload_json=result.to_output(),
            current_user=current_user,
        )
        return result

    def _step_build_evidence_summary(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        media_ids: list[UUID],
        results: dict[str, AgentToolResult],
    ) -> list[AgentArtifact]:
        step = self.create_step(
            run_id=run.run_id,
            step_index=6,
            step_type="artifact_generation",
            step_name="build_evidence_summary",
            status="running",
            input_json={"tool_statuses": self._status_counts(results.values())},
            reasoning_summary="Summarize OCR, visual analysis, blocked providers, and safety guard outputs into auditable artifacts.",
        )
        evidence_summary = self._build_multimodal_summary(media_ids, results, payload)
        safety_checklist = self._build_safety_checklist(results)
        artifacts = [
            self._create_artifact(
                run=run,
                artifact_type="multimodal_evidence_summary",
                title="多模态证据摘要",
                content_text="多模态证据摘要已生成，机器识别结果仅作为辅助证据，需人工复核。",
                content_json=evidence_summary,
            ),
            self._create_artifact(
                run=run,
                artifact_type="safety_checklist",
                title="光伏逆变器检修安全复核清单",
                content_text="安全复核清单已生成，现场作业前必须确认断电、验电和绝缘防护。",
                content_json=safety_checklist,
            ),
        ]
        step.status = "succeeded"
        step.output_json = {
            "artifact_types": [item.artifact_type for item in artifacts],
            "mocked": evidence_summary.get("mocked"),
            "requires_human_review": True,
        }
        step.finished_at = self.now()
        self.repository.update_step(step)
        self.db.commit()
        self.create_event(
            run_id=run.run_id,
            event_type="artifacts_created",
            event_message="Multimodal evidence summary and safety checklist artifacts created",
            payload_json={"artifact_ids": [str(item.id) for item in artifacts]},
            current_user=current_user,
        )
        return artifacts

    def _step_create_evidence_links(
        self,
        run: AgentRun,
        current_user: User,
        media_ids: list[UUID],
        artifacts: list[AgentArtifact],
        results: dict[str, AgentToolResult],
    ) -> list[str]:
        step = self.create_step(
            run_id=run.run_id,
            step_index=7,
            step_type="evidence_linking",
            step_name="create_evidence_links",
            status="running",
            input_json={"media_ids": [str(item) for item in media_ids], "artifact_ids": [str(item.id) for item in artifacts]},
            reasoning_summary="Create traceable media evidence links to the agent run and generated artifacts.",
        )
        link_ids: list[str] = []
        errors: list[str] = []
        evidence_service = MultimodalEvidenceService(self.db)
        for media_id in media_ids:
            for payload in self._link_payloads(media_id, run, artifacts, results):
                try:
                    link = evidence_service.create_evidence_link(payload, current_user)
                    link_ids.append(str(link.id))
                except MultimodalEvidenceServiceError as exc:
                    errors.append(str(exc))

        trace_artifact = self._create_artifact(
            run=run,
            artifact_type="evidence_trace_summary",
            title="证据追溯摘要",
            content_text="证据追溯摘要已生成，可追溯到媒体、Agent Run、工具调用和 artifact。",
            content_json=self._build_trace_summary(run, media_ids, link_ids, results),
        )
        artifacts.append(trace_artifact)
        for media_id in media_ids:
            try:
                link = evidence_service.create_evidence_link(
                    MediaEvidenceLinkCreate(
                        media_id=media_id,
                        source_type="agent_artifact",
                        source_id=str(trace_artifact.id),
                        relation_type="generated_from",
                    ),
                    current_user,
                )
                link_ids.append(str(link.id))
            except MultimodalEvidenceServiceError as exc:
                errors.append(str(exc))

        trace_artifact.content_json = self._build_trace_summary(run, media_ids, link_ids, results)
        self.repository.create_artifact(trace_artifact)
        step.status = "succeeded" if link_ids else "blocked"
        step.output_json = {"evidence_link_ids": link_ids, "errors": errors, "trace_artifact_id": str(trace_artifact.id)}
        step.error_message = "; ".join(errors) if errors and not link_ids else None
        step.finished_at = self.now()
        self.repository.update_step(step)
        self.db.commit()
        self.create_event(
            run_id=run.run_id,
            event_type="evidence_links_created",
            event_message=f"Created {len(link_ids)} media evidence links",
            payload_json={"evidence_link_ids": link_ids, "errors": errors},
            current_user=current_user,
        )
        return link_ids

    def _step_finalize_run(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
        evidence_link_ids: list[str],
    ) -> None:
        status_counts = self._status_counts(results.values())
        final_answer = self._build_final_answer(payload, results, artifacts, evidence_link_ids)
        requires_approval = payload.requires_approval
        run.status = "waiting_approval" if requires_approval else self._run_status(results)
        run.requires_human_approval = requires_approval
        run.approval_status = "pending" if requires_approval else "not_required"
        run.final_answer = final_answer
        run.confidence = self._confidence(results)
        run.finished_at = None if run.status == "waiting_approval" else self.now()
        self.repository.update_run(run)
        if requires_approval:
            self.repository.create_approval(
                AgentApproval(
                    run_id=run.run_id,
                    approval_type="human_review",
                    requested_action="approve_multimodal_evidence_agent_result",
                    payload_json={"artifact_ids": [str(item.id) for item in artifacts], "status_counts": status_counts},
                    status="pending",
                    requested_by=current_user.id,
                )
            )
        self.create_step(
            run_id=run.run_id,
            step_index=8,
            step_type="finalization",
            step_name="finalize_run",
            status=run.status,
            input_json={"status_counts": status_counts, "artifact_count": len(artifacts)},
            output_json={
                "final_answer": final_answer,
                "status": run.status,
                "confidence": float(run.confidence or 0),
                "evidence_link_count": len(evidence_link_ids),
            },
            reasoning_summary="Finalize the run with succeeded, blocked, mocked, review-needed, and next-step boundaries.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="run_completed",
            event_message="Multimodal evidence agent orchestration completed",
            payload_json={
                "status": run.status,
                "tool_status_counts": status_counts,
                "artifact_ids": [str(item.id) for item in artifacts],
                "evidence_link_ids": evidence_link_ids,
                "external_api_called": False,
            },
            current_user=current_user,
        )
        self.db.commit()

    def _create_artifact(
        self,
        *,
        run: AgentRun,
        artifact_type: str,
        title: str,
        content_text: str,
        content_json: dict[str, Any],
    ) -> AgentArtifact:
        artifact = self.repository.create_artifact(
            AgentArtifact(
                run_id=run.run_id,
                artifact_type=artifact_type,
                title=title,
                content_text=content_text,
                content_json=json_safe(content_json),
                source_type="agent_run",
                source_id=run.run_id,
            )
        )
        self.db.commit()
        return artifact

    def _link_payloads(
        self,
        media_id: UUID,
        run: AgentRun,
        artifacts: list[AgentArtifact],
        results: dict[str, AgentToolResult],
    ) -> list[MediaEvidenceLinkCreate]:
        ocr_result_id = self._first_uuid(self._ocr_result_ids(results))
        analysis_id = self._first_uuid(self._analysis_ids(results))
        payloads = [
            MediaEvidenceLinkCreate(
                media_id=media_id,
                ocr_result_id=ocr_result_id,
                analysis_id=analysis_id,
                source_type="agent_run",
                source_id=run.run_id,
                relation_type="used_as_context",
            )
        ]
        for artifact in artifacts:
            payloads.append(
                MediaEvidenceLinkCreate(
                    media_id=media_id,
                    ocr_result_id=ocr_result_id,
                    analysis_id=analysis_id,
                    source_type="agent_artifact",
                    source_id=str(artifact.id),
                    relation_type="generated_from",
                )
            )
        return payloads

    def _build_tool_payload(self, payload: AgentRunCreateRequest, tool_name: str, media_ids: list[UUID]) -> dict[str, Any]:
        specific = payload.tool_inputs.get(tool_name, {}) if payload.tool_inputs else {}
        return {
            **payload.context,
            **specific,
            "input_text": payload.input_text,
            "question": specific.get("question") or payload.input_text,
            "query": specific.get("query") or payload.input_text,
            "device_id": str(payload.device_id) if payload.device_id else None,
            "media_ids": [str(media_id) for media_id in media_ids],
            "dry_run": payload.dry_run,
            "mock_run": payload.mock_run,
            "agent_code": payload.agent_code,
        }

    def _build_multimodal_summary(
        self,
        media_ids: list[UUID],
        results: dict[str, AgentToolResult],
        payload: AgentRunCreateRequest,
    ) -> dict[str, Any]:
        ocr_context = self._result_list(results.get("media_ocr"), "ocr_context")
        analyses = self._result_list(results.get("media_mimo_analysis"), "analyses")
        safety_data = (results.get("safety_guard").data if results.get("safety_guard") else {}) or {}
        visible_text = [str(item.get("text") or item.get("detected_text") or "")[:500] for item in ocr_context]
        visual_findings = self._merge_list(analyses, "visual_findings_json")
        possible_faults = self._merge_list(analyses, "possible_faults_json")
        alarm_codes = self._merge_list(analyses, "detected_alarm_codes_json")
        safety_risks = self._merge_list(analyses, "safety_risks_json") or safety_data.get("warnings") or []
        recommended = self._merge_list(analyses, "recommended_actions_json") or [
            {"action": "现场人员复核告警代码、直流侧状态、交流并网状态和逆变器运行日志。"},
            {"action": "按厂家手册确认安全隔离后再执行检修。"},
        ]
        limitations = self._merge_list(analyses, "limitations_json") or [
            "本次编排不调用真实 mimo、云端视觉或 OCR API。",
            "机器证据只能作为辅助线索，不能替代现场工程师判断。",
        ]
        mocked = any(self._is_mocked(result) for result in results.values())
        return {
            "media_ids": [str(item) for item in media_ids],
            "ocr_status": (results.get("media_ocr").status if results.get("media_ocr") else "skipped"),
            "visual_analysis_status": (
                results.get("media_mimo_analysis").status if results.get("media_mimo_analysis") else "skipped"
            ),
            "image_type": payload.context.get("image_type") or "pv_inverter_field_image",
            "visible_text": [item for item in visible_text if item],
            "detected_alarm_codes": alarm_codes,
            "visual_findings": visual_findings,
            "possible_fault_clues": possible_faults,
            "safety_risks": safety_risks,
            "recommended_next_steps": recommended,
            "limitations": limitations,
            "mocked": mocked,
            "dry_run": payload.dry_run,
            "external_api_called": False,
            "requires_human_review": True,
        }

    def _build_safety_checklist(self, results: dict[str, AgentToolResult]) -> dict[str, Any]:
        data = (results.get("safety_guard").data if results.get("safety_guard") else {}) or {}
        return {
            "must_do": data.get("must_do")
            or [
                "断开直流侧和交流侧电源并挂牌上锁。",
                "使用合格验电器确认无电压和残余电荷。",
                "佩戴绝缘手套、绝缘鞋、护目镜等防护用品。",
            ],
            "risk_level": data.get("risk_level") or "medium",
            "warnings": data.get("warnings") or data.get("safety_notes") or [],
            "notices": data.get("notices")
            or [
                "本清单为作业辅助，不替代华为/阳光电源厂家手册和现场安全规程。",
                "如存在潮湿、过温、烧蚀、异味或绝缘异常，应升级为高风险复核。",
            ],
            "requires_field_engineer_confirmation": True,
        }

    def _build_trace_summary(
        self,
        run: AgentRun,
        media_ids: list[UUID],
        evidence_link_ids: list[str],
        results: dict[str, AgentToolResult],
    ) -> dict[str, Any]:
        calls = self.repository.list_tool_calls(run.run_id)
        return {
            "agent_run_id": run.run_id,
            "media_ids": [str(item) for item in media_ids],
            "job_ids": self._job_ids(results),
            "ocr_result_ids": self._ocr_result_ids(results),
            "analysis_ids": self._analysis_ids(results),
            "external_trace_ids": self._external_trace_ids(results),
            "tool_call_ids": [str(item.id) for item in calls],
            "evidence_link_ids": evidence_link_ids,
            "external_api_called": False,
        }

    def _build_final_answer(
        self,
        payload: AgentRunCreateRequest,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
        evidence_link_ids: list[str],
    ) -> str:
        succeeded = [name for name, result in results.items() if result.status in {"succeeded", "waiting_approval"}]
        blocked = [name for name, result in results.items() if result.status == "blocked"]
        skipped = [name for name, result in results.items() if result.status == "skipped"]
        mocked = [name for name, result in results.items() if self._is_mocked(result)]
        external_blocked = all(results.get(name) and results[name].status == "blocked" for name in ["media_ocr", "media_mimo_analysis"])
        lines = [
            "多模态证据智能体运行已完成受控编排。",
            f"现场说明：{(payload.input_text or '未提供')[:260]}",
            f"成功工具：{', '.join(succeeded) if succeeded else '无'}。",
            f"Blocked 工具：{', '.join(blocked) if blocked else '无'}。",
            f"Skipped 工具：{', '.join(skipped) if skipped else '无'}。",
            f"Mocked 结果：{', '.join(mocked) if mocked else '无'}。",
            f"生成 artifact：{', '.join(item.artifact_type for item in artifacts)}。",
            f"证据链数量：{len(evidence_link_ids)}。",
            "机器 OCR / 图像分析仅作为辅助证据，必须由现场工程师或专家复核。",
            "本次未调用真实 mimo、云端视觉、OCR 或本地模型 API，external_api_called=false。",
        ]
        if external_blocked:
            lines.append("外部识别能力未配置：OCR 与 mimo-2.5/视觉分析 provider 当前 blocked，只能使用已有或 mocked 证据。")
        lines.append("下一步建议：复核媒体证据、核对厂家手册和告警代码，在确认断电、验电和绝缘防护后再执行现场作业。")
        return "\n".join(lines)

    @staticmethod
    def _compact_tool_data(result: AgentToolResult | None) -> dict[str, Any]:
        if not result:
            return {}
        return {"status": result.status, "summary": result.summary, "data_keys": sorted((result.data or {}).keys())}

    @staticmethod
    def _status_counts(results: Any) -> dict[str, int]:
        counts: dict[str, int] = {}
        for result in results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts

    @staticmethod
    def _run_status(results: dict[str, AgentToolResult]) -> str:
        statuses = {result.status for result in results.values()}
        if statuses == {"failed"}:
            return "failed"
        if statuses.issubset({"blocked", "skipped"}):
            return "blocked"
        return "succeeded"

    @staticmethod
    def _confidence(results: dict[str, AgentToolResult]) -> Decimal:
        values = list(results.values())
        if not values:
            return Decimal("0.1000")
        succeeded = sum(1 for item in values if item.status in {"succeeded", "waiting_approval"})
        blocked = sum(1 for item in values if item.status == "blocked")
        score = 0.30 + 0.35 * (succeeded / len(values)) - 0.04 * blocked
        return Decimal(f"{max(0.18, min(0.78, score)):.4f}")

    @staticmethod
    def _result_list(result: AgentToolResult | None, key: str) -> list[dict[str, Any]]:
        if not result:
            return []
        value = (result.data or {}).get(key)
        return value if isinstance(value, list) else []

    @staticmethod
    def _merge_list(items: list[dict[str, Any]], key: str) -> list[Any]:
        merged: list[Any] = []
        for item in items:
            value = item.get(key)
            if isinstance(value, list):
                merged.extend(value)
            elif value:
                merged.append(value)
        return merged

    @staticmethod
    def _is_mocked(result: AgentToolResult) -> bool:
        data = result.data or {}
        if data.get("mocked") is True or data.get("source") in {"mocked_ocr", "mocked_analysis"}:
            return True
        for key in ("ocr_context", "analyses"):
            value = data.get(key)
            if isinstance(value, list) and any(((item.get("raw_response_json") or {}).get("mocked") is True) for item in value):
                return True
        return False

    @staticmethod
    def _job_ids(results: dict[str, AgentToolResult]) -> list[str]:
        ids: list[str] = []
        for result in results.values():
            data = result.data or {}
            for key in ("ocr_context", "analyses", "processing_jobs"):
                value = data.get(key)
                if not isinstance(value, list):
                    continue
                for item in value:
                    job_id = item.get("job_id") or item.get("id") if key == "processing_jobs" else item.get("job_id")
                    if job_id and str(job_id) not in ids:
                        ids.append(str(job_id))
        return ids

    @staticmethod
    def _ocr_result_ids(results: dict[str, AgentToolResult]) -> list[str]:
        ids: list[str] = []
        for item in MultimodalEvidenceAgentOrchestrator._result_list(results.get("media_ocr"), "ocr_context"):
            if item.get("id") and str(item["id"]) not in ids:
                ids.append(str(item["id"]))
        return ids

    @staticmethod
    def _analysis_ids(results: dict[str, AgentToolResult]) -> list[str]:
        ids: list[str] = []
        for item in MultimodalEvidenceAgentOrchestrator._result_list(results.get("media_mimo_analysis"), "analyses"):
            if item.get("id") and str(item["id"]) not in ids:
                ids.append(str(item["id"]))
        return ids

    @staticmethod
    def _external_trace_ids(results: dict[str, AgentToolResult]) -> list[str]:
        ids: list[str] = []
        for result in results.values():
            data = result.data or {}
            for key in ("ocr_context", "analyses", "processing_jobs"):
                value = data.get(key)
                if isinstance(value, list):
                    for item in value:
                        trace_id = item.get("external_trace_id")
                        if trace_id and str(trace_id) not in ids:
                            ids.append(str(trace_id))
            gateway = data.get("external_api_gateway")
            if isinstance(gateway, dict) and gateway.get("trace_id") and str(gateway["trace_id"]) not in ids:
                ids.append(str(gateway["trace_id"]))
        return ids

    @staticmethod
    def _first_uuid(values: list[str]) -> UUID | None:
        if not values:
            return None
        try:
            return UUID(str(values[0]))
        except (TypeError, ValueError):
            return None
