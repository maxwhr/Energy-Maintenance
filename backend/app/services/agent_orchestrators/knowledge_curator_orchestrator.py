from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models import AgentArtifact, AgentRun, User
from app.schemas.agent import AgentRunCreateRequest, AgentRunRead
from app.services.agent_orchestrators.base import AgentOrchestratorError
from app.services.agent_orchestrators.workflow_base import WorkflowAgentOrchestrator
from app.services.agent_tools.base import AgentToolResult


class KnowledgeCuratorOrchestrator(WorkflowAgentOrchestrator):
    DEFAULT_TOOLS = [
        "device_lookup",
        "device_history",
        "record_center_lookup",
        "knowledge_search",
        "kg_business_context",
        "media_lookup",
        "safety_guard",
        "knowledge_contribution_draft_creator",
        "human_approval",
    ]

    def create_run(self, payload: AgentRunCreateRequest, *, current_user: User) -> AgentRunRead:
        self.validate_creator(payload, current_user)
        if not payload.input_text:
            raise AgentOrchestratorError("knowledge_curator_agent requires input_text")

        selected_tools = self.selected_tools(payload, self.DEFAULT_TOOLS)
        definition = self.require_definition_and_tools(payload.agent_code, selected_tools)
        run = self.create_agent_run(
            payload,
            current_user,
            mode="knowledge_curator_draft",
            provider=definition.default_model_provider or "rule_based",
            model_name=definition.default_model_name or "knowledge_curator_orchestrator_v1",
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
            reasoning_summary="Load PV inverter device context for knowledge curation draft.",
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
            reasoning_summary="Load maintenance history to identify reusable experience patterns.",
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
            reasoning_summary="Read record-center context without modifying any record.",
        )
        source_context = self._load_source_agent_artifacts(run, payload, current_user, step_index=5)
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=6,
            step_name="load_media_evidence",
            tool_name="media_lookup",
            reasoning_summary="Load selected media evidence and multimodal summaries when available.",
            optional=True,
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=7,
            step_name="search_existing_knowledge",
            tool_name="knowledge_search",
            reasoning_summary="Search approved/parsed/active knowledge to detect duplicate or similar cases.",
        )
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=8,
            step_name="query_kg_context",
            tool_name="kg_business_context",
            reasoning_summary="Read existing knowledge graph context and generate suggestions only as artifacts.",
        )
        safety_payload = {
            **self.build_tool_payload(payload, "safety_guard"),
            "source": "knowledge_curator_agent",
            "source_artifact_types": [item.get("artifact_type") for item in source_context["artifacts"]],
        }
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=9,
            step_name="run_safety_guard",
            tool_name="safety_guard",
            reasoning_summary="Generate conservative safety boundaries for experience curation.",
            override_payload=safety_payload,
        )

        case_artifact = self._build_maintenance_case_summary(
            run, payload, current_user, results, source_context, step_index=10
        )
        draft_artifact = self._build_knowledge_contribution_draft(
            run,
            payload,
            current_user,
            results,
            source_context,
            case_artifact,
            step_index=11,
            selected_tools=selected_tools,
        )
        kg_artifact = self._build_kg_candidate_suggestion(
            run, payload, current_user, results, source_context, step_index=12
        )
        safety_artifact = self._build_safety_artifact(run, current_user, results)
        artifacts = [case_artifact, draft_artifact, kg_artifact, safety_artifact]

        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=13,
            step_name="prepare_human_approval",
            tool_name="human_approval",
            reasoning_summary="Record that human approval is required before any formal knowledge conversion.",
            override_payload={"draft_artifact_id": str(draft_artifact.id), "conversion_task": "Task 22J"},
        )
        approval = self.create_approval(
            run=run,
            approval_type="knowledge_contribution_draft_review",
            requested_action="review_knowledge_contribution_draft",
            payload_json={
                "artifact_type": "knowledge_contribution_draft",
                "artifact_id": str(draft_artifact.id),
                "source_agent_run_id": run.run_id,
                "requires_expert_review": True,
                "can_convert_to_formal_contribution": False,
                "conversion_task": "Task 22J",
                "formal_contribution_created": False,
                "formal_document_created": False,
                "approved_chunks_created": False,
                "formal_kg_write_created": False,
            },
            current_user=current_user,
        )
        self.create_step(
            run_id=run.run_id,
            step_index=14,
            step_type="approval",
            step_name="create_approval_request",
            status="waiting_approval",
            input_json={"approval_type": "knowledge_contribution_draft_review"},
            output_json={"approval_id": str(approval.id), "status": approval.status, "conversion_task": "Task 22J"},
            reasoning_summary="Create approval for knowledge contribution draft; approval does not convert it to formal knowledge.",
        )
        trace_artifact = self._build_evidence_trace(
            run,
            payload,
            current_user,
            results,
            source_context,
            [*artifacts],
            [approval.id],
            step_index=15,
        )
        artifacts.append(trace_artifact)
        self.finalize(
            run=run,
            current_user=current_user,
            results=results,
            artifacts=artifacts,
            final_answer=self._final_answer(payload, results, artifacts, source_context),
            confidence=self._confidence(results, artifacts),
            requires_approval=True,
            approval_status="pending",
            step_index=16,
            step_name="finalize_curator_run",
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
            step_name="validate_curator_input",
            status="succeeded",
            input_json={
                "agent_code": payload.agent_code,
                "role": current_user.role,
                "device_id": str(payload.device_id) if payload.device_id else None,
                "media_count": len(payload.requested_media_ids()),
                "source_agent_run_ids": self._string_list(payload.context.get("source_agent_run_ids")),
                "source_artifact_ids": self._string_list(payload.context.get("source_artifact_ids")),
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
            },
            output_json={
                "selected_tools": selected_tools,
                "draft_only": True,
                "formal_contribution_created": False,
                "formal_document_created": False,
                "approved_chunks_created": False,
                "formal_kg_write_created": False,
                "external_api_called": False,
            },
            reasoning_summary="Knowledge curation input, RBAC role, source IDs, and draft-only boundaries were validated.",
        )

    def _load_source_agent_artifacts(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        *,
        step_index: int,
    ) -> dict[str, Any]:
        run_ids = self._string_list(payload.context.get("source_agent_run_ids"))
        artifact_ids = self._uuid_list(payload.context.get("source_artifact_ids"))
        source_runs: list[dict[str, Any]] = []
        source_artifacts: list[dict[str, Any]] = []
        limitations: list[str] = []

        for run_id in run_ids:
            source_run = self.repository.get_run(run_id)
            if not source_run:
                limitations.append(f"source_agent_run_id not found: {run_id}")
                continue
            source_runs.append(
                {
                    "run_id": source_run.run_id,
                    "agent_code": source_run.agent_code,
                    "status": source_run.status,
                    "final_answer": source_run.final_answer,
                }
            )
            for artifact in self.repository.list_artifacts(source_run.run_id):
                source_artifacts.append(self._artifact_payload(artifact))

        for artifact in self.repository.list_artifacts_by_ids(artifact_ids):
            payload_item = self._artifact_payload(artifact)
            if payload_item not in source_artifacts:
                source_artifacts.append(payload_item)

        missing_artifacts = {str(item) for item in artifact_ids} - {item["id"] for item in source_artifacts}
        limitations.extend(f"source_artifact_id not found: {item}" for item in sorted(missing_artifacts))
        if not run_ids and not artifact_ids:
            limitations.append("No source agent run or source artifact was provided; draft evidence is limited to current input.")

        context = {"runs": source_runs, "artifacts": source_artifacts, "limitations": limitations}
        self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="context_loading",
            step_name="load_source_agent_artifacts",
            status="succeeded" if source_runs or source_artifacts else "skipped",
            input_json={"source_agent_run_ids": run_ids, "source_artifact_ids": [str(item) for item in artifact_ids]},
            output_json={
                "source_run_count": len(source_runs),
                "source_artifact_count": len(source_artifacts),
                "limitations": limitations,
            },
            reasoning_summary="Load source diagnosis, SOP, task, multimodal, safety, and trace artifacts when provided.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="orchestration_step",
            event_message="load_source_agent_artifacts completed",
            payload_json={"source_run_count": len(source_runs), "source_artifact_count": len(source_artifacts)},
            current_user=current_user,
        )
        return context

    def _build_maintenance_case_summary(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
        source_context: dict[str, Any],
        *,
        step_index: int,
    ) -> AgentArtifact:
        safety = self.result_data(results, "safety_guard")
        device = self.compact_device(self.result_data(results, "device_lookup"))
        knowledge = self.result_data(results, "knowledge_search")
        media = self.result_data(results, "media_lookup")
        extracted = self._extract_source_summaries(source_context)
        limitations = self._limitations(source_context, results)
        if not extracted.get("diagnosis_summary"):
            limitations.append("No diagnosis_summary source artifact was found; case summary uses current input.")
        summary = {
            "case_title": self._case_title(payload),
            "device_id": str(run.device_id) if run.device_id else None,
            "manufacturer": payload.context.get("manufacturer") or device.get("manufacturer"),
            "product_series": payload.context.get("product_series") or device.get("product_series"),
            "fault_type": payload.context.get("fault_type"),
            "alarm_code": payload.context.get("alarm_code"),
            "symptom": payload.input_text or payload.context.get("fault_description") or "",
            "environment_context": payload.context.get("environment_context") or payload.context.get("engineer_notes") or "",
            "diagnosis_summary": extracted.get("diagnosis_summary") or payload.input_text or "",
            "root_cause_candidates": extracted.get("root_cause_candidates") or [],
            "inspection_process": extracted.get("inspection_process") or [],
            "solution_summary": extracted.get("solution_summary") or "",
            "verification_result": payload.context.get("verification_result") or "",
            "safety_notes": safety.get("safety_notes") or [],
            "media_evidence": media.get("items") or [],
            "source_agent_runs": [item.get("run_id") for item in source_context.get("runs", [])],
            "source_artifacts": [item.get("id") for item in source_context.get("artifacts", [])],
            "knowledge_references": knowledge.get("references") or [],
            "confidence": self._confidence(results, []),
            "requires_human_review": True,
            "limitations": limitations,
        }
        artifact = self.create_artifact(
            run=run,
            artifact_type="maintenance_case_summary",
            title="维修经验案例草稿",
            content_text="已生成维修经验案例草稿，仅用于专家审核前的知识沉淀，不是正式知识库内容。",
            content_json=summary,
        )
        self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="artifact_generation",
            step_name="build_maintenance_case_summary",
            status="succeeded",
            input_json={"source_artifact_count": len(source_context.get("artifacts", []))},
            output_json={"artifact_id": str(artifact.id), "artifact_type": artifact.artifact_type},
            reasoning_summary="Summarize maintenance experience from source artifacts, records, media, safety, and engineer notes.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifact_created",
            event_message="maintenance_case_summary artifact created",
            payload_json={"artifact_id": str(artifact.id)},
            current_user=current_user,
        )
        return artifact

    def _build_knowledge_contribution_draft(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
        source_context: dict[str, Any],
        case_artifact: AgentArtifact,
        *,
        step_index: int,
        selected_tools: list[str],
    ) -> AgentArtifact:
        case_summary = case_artifact.content_json or {}
        safety = self.result_data(results, "safety_guard")
        knowledge = self.result_data(results, "knowledge_search")
        kg = self.result_data(results, "kg_business_context")
        duplicate = self._duplicate_risk(knowledge)
        boundary = self._evidence_boundary(results, source_context)
        limitations = self._limitations(source_context, results)
        if duplicate["has_similar_knowledge"]:
            limitations.append("Potential duplicate knowledge exists and must be confirmed by expert review.")
        if boundary["mocked_evidence_used"]:
            limitations.append("Mocked evidence is included and cannot be converted to formal knowledge directly.")
        if boundary["unreviewed_ai_evidence_used"]:
            limitations.append("AI/image evidence is not fully human-accepted and requires review.")
        override_payload = {
            **self.build_tool_payload(payload, "knowledge_contribution_draft_creator"),
            "title": f"{self._case_title(payload)} 知识贡献草稿",
            "category": "maintenance_experience",
            "maintenance_case_summary": case_summary,
            "problem_description": case_summary.get("symptom"),
            "cause_analysis": case_summary.get("diagnosis_summary"),
            "troubleshooting_steps": case_summary.get("inspection_process") or [],
            "solution": case_summary.get("solution_summary"),
            "safety_precautions": safety.get("safety_notes") or [],
            "related_media_ids": [str(item) for item in payload.requested_media_ids()],
            "source_agent_run_ids": [item.get("run_id") for item in source_context.get("runs", [])],
            "source_artifact_ids": [item.get("id") for item in source_context.get("artifacts", [])],
            "knowledge_references": knowledge.get("references") or [],
            "kg_context": self._kg_summary(kg),
            "duplicate_risk": duplicate,
            "mocked_evidence_used": boundary["mocked_evidence_used"],
            "unreviewed_ai_evidence_used": boundary["unreviewed_ai_evidence_used"],
            "draft_quality_score": self._quality_score(results, source_context),
            "limitations": limitations,
        }
        self.execute_tool_step(
            run=run,
            payload=payload,
            current_user=current_user,
            selected_tools=selected_tools,
            results=results,
            step_index=step_index,
            step_name="build_knowledge_contribution_draft",
            tool_name="knowledge_contribution_draft_creator",
            reasoning_summary="Generate a knowledge contribution draft artifact payload without formal knowledge writes.",
            override_payload=override_payload,
        )
        draft = self.result_data(results, "knowledge_contribution_draft_creator").get("knowledge_contribution_draft")
        if not isinstance(draft, dict):
            draft = {"title": override_payload["title"], "limitations": limitations, "requires_expert_review": True}
        artifact = self.create_artifact(
            run=run,
            artifact_type="knowledge_contribution_draft",
            title="知识贡献草稿",
            content_text="知识贡献草稿已生成，等待专家审核；本任务不会转正式知识库。",
            content_json=draft,
            source_type="agent_tool",
            source_id="knowledge_contribution_draft_creator",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifact_created",
            event_message="knowledge_contribution_draft artifact created",
            payload_json={"artifact_id": str(artifact.id), "draft_only": True},
            current_user=current_user,
        )
        return artifact

    def _build_kg_candidate_suggestion(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
        source_context: dict[str, Any],
        *,
        step_index: int,
    ) -> AgentArtifact:
        kg = self.result_data(results, "kg_business_context")
        fault_type = payload.context.get("fault_type") or "unknown_fault"
        alarm_code = payload.context.get("alarm_code")
        candidate_nodes = [
            {
                "node_type": "fault",
                "name": str(fault_type),
                "description": "Fault type from curated PV inverter maintenance experience.",
                "confidence": 0.62,
            }
        ]
        if alarm_code:
            candidate_nodes.append(
                {
                    "node_type": "symptom",
                    "name": str(alarm_code),
                    "description": "Alarm code or symptom from source maintenance experience.",
                    "confidence": 0.58,
                }
            )
        for item in (kg.get("related_causes") or [])[:3]:
            if isinstance(item, dict):
                candidate_nodes.append(
                    {
                        "node_type": "cause",
                        "name": str(item.get("name") or item.get("title") or "related_cause"),
                        "description": str(item.get("description") or ""),
                        "confidence": 0.50,
                    }
                )
        candidate_edges = []
        if alarm_code:
            candidate_edges.append(
                {"source": str(fault_type), "relation": "HAS_SYMPTOM", "target": str(alarm_code), "confidence": 0.58}
            )
        for node in candidate_nodes:
            if node["node_type"] == "cause":
                candidate_edges.append(
                    {"source": str(fault_type), "relation": "CAUSED_BY", "target": node["name"], "confidence": 0.48}
                )
        suggestion = {
            "candidate_nodes": candidate_nodes,
            "candidate_edges": candidate_edges,
            "evidence_sources": [
                *[item.get("id") for item in source_context.get("artifacts", [])],
                *[str(item) for item in payload.requested_media_ids()],
            ],
            "kg_context_summary": self._kg_summary(kg),
            "requires_kg_review": True,
            "formal_kg_write_created": False,
            "limitations": [
                "KG candidates are suggestions only and are not written to formal graph nodes or edges.",
                *self._limitations(source_context, results),
            ],
        }
        artifact = self.create_artifact(
            run=run,
            artifact_type="kg_candidate_suggestion",
            title="知识图谱候选建议",
            content_text="已生成知识图谱候选节点和关系建议，仅供专家审核，不写入正式图谱。",
            content_json=suggestion,
        )
        self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="artifact_generation",
            step_name="build_kg_candidate_suggestion",
            status="succeeded",
            input_json={"kg_summary": kg.get("summary")},
            output_json={"artifact_id": str(artifact.id), "formal_kg_write_created": False},
            reasoning_summary="Build graph node and edge candidates as an artifact only.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifact_created",
            event_message="kg_candidate_suggestion artifact created",
            payload_json={"artifact_id": str(artifact.id), "formal_kg_write_created": False},
            current_user=current_user,
        )
        return artifact

    def _build_safety_artifact(
        self,
        run: AgentRun,
        current_user: User,
        results: dict[str, AgentToolResult],
    ) -> AgentArtifact:
        safety = self.result_data(results, "safety_guard")
        checklist = {
            "must_do": safety.get("must_do") or [],
            "risk_level": safety.get("risk_level") or "medium",
            "safety_precautions": safety.get("safety_notes") or [],
            "warnings": safety.get("warnings") or [],
            "notices": safety.get("notices") or [],
        }
        artifact = self.create_artifact(
            run=run,
            artifact_type="safety_checklist",
            title="知识沉淀安全注意事项",
            content_text="已生成知识沉淀安全注意事项，正式入库前必须由专家复核。",
            content_json=checklist,
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifact_created",
            event_message="safety_checklist artifact created for knowledge curation",
            payload_json={"artifact_id": str(artifact.id)},
            current_user=current_user,
        )
        return artifact

    def _build_evidence_trace(
        self,
        run: AgentRun,
        payload: AgentRunCreateRequest,
        current_user: User,
        results: dict[str, AgentToolResult],
        source_context: dict[str, Any],
        artifacts: list[AgentArtifact],
        approval_ids: list[UUID],
        *,
        step_index: int,
    ) -> AgentArtifact:
        knowledge = self.result_data(results, "knowledge_search")
        kg = self.result_data(results, "kg_business_context")
        trace = self.trace_summary(
            run=run,
            results=results,
            artifacts=artifacts,
            media_ids=payload.requested_media_ids(),
            extra={
                "source_agent_run_ids": [item.get("run_id") for item in source_context.get("runs", [])],
                "source_artifact_ids": [item.get("id") for item in source_context.get("artifacts", [])],
                "diagnosis_trace_ids": self._source_trace_ids(source_context),
                "sop_artifact_ids": self._source_artifact_ids_by_type(source_context, "sop_draft"),
                "task_artifact_ids": self._source_artifact_ids_by_type(source_context, "task_draft"),
                "knowledge_reference_ids": [
                    str(item.get("document_id") or item.get("chunk_id") or item.get("id"))
                    for item in knowledge.get("references") or []
                ],
                "kg_reference_ids": [
                    str(item.get("id") or item.get("source") or item.get("target"))
                    for item in kg.get("evidence") or []
                ],
                "approval_ids": [str(item) for item in approval_ids],
                "formal_contribution_created": False,
                "formal_document_created": False,
                "approved_chunks_created": False,
                "formal_kg_write_created": False,
                "limitations": self._limitations(source_context, results),
            },
        )
        artifact = self.create_artifact(
            run=run,
            artifact_type="evidence_trace_summary",
            title="知识沉淀证据追溯摘要",
            content_text="已生成知识沉淀证据追溯摘要，可追踪来源 run、artifact、媒体、知识引用、图谱上下文和审批记录。",
            content_json=trace,
        )
        self.create_step(
            run_id=run.run_id,
            step_index=step_index,
            step_type="evidence_linking",
            step_name="create_evidence_trace",
            status="succeeded",
            input_json={"artifact_types": [item.artifact_type for item in artifacts]},
            output_json={"artifact_id": str(artifact.id), "approval_ids": [str(item) for item in approval_ids]},
            reasoning_summary="Create trace summary for the draft-only knowledge curation flow.",
        )
        self.create_event(
            run_id=run.run_id,
            event_type="artifact_created",
            event_message="evidence_trace_summary artifact created for knowledge curation",
            payload_json={"artifact_id": str(artifact.id)},
            current_user=current_user,
        )
        return artifact

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @classmethod
    def _uuid_list(cls, value: Any) -> list[UUID]:
        result: list[UUID] = []
        for item in cls._string_list(value):
            try:
                parsed = UUID(str(item))
            except (TypeError, ValueError):
                continue
            if parsed not in result:
                result.append(parsed)
        return result

    @staticmethod
    def _artifact_payload(artifact: AgentArtifact) -> dict[str, Any]:
        return {
            "id": str(artifact.id),
            "run_id": artifact.run_id,
            "artifact_type": artifact.artifact_type,
            "title": artifact.title,
            "content_text": artifact.content_text,
            "content_json": artifact.content_json or {},
            "source_type": artifact.source_type,
            "source_id": artifact.source_id,
        }

    @staticmethod
    def _case_title(payload: AgentRunCreateRequest) -> str:
        manufacturer = payload.context.get("manufacturer") or "PV inverter"
        series = payload.context.get("product_series") or ""
        fault = payload.context.get("fault_type") or "maintenance experience"
        return f"{manufacturer} {series} {fault}".strip()

    @staticmethod
    def _kg_summary(kg: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": kg.get("summary") or {},
            "related_causes": (kg.get("related_causes") or [])[:5],
            "inspection_items": (kg.get("inspection_items") or [])[:5],
            "recommended_actions": (kg.get("recommended_actions") or [])[:5],
            "safety_risks": (kg.get("safety_risks") or [])[:5],
            "evidence": (kg.get("evidence") or [])[:5],
        }

    @staticmethod
    def _duplicate_risk(knowledge: dict[str, Any]) -> dict[str, Any]:
        references = knowledge.get("references") or []
        diagnostics = knowledge.get("retrieval_diagnostics") or {}
        vector_available = bool(knowledge.get("vector_available") or diagnostics.get("vector_available"))
        retrieval_mode = str(knowledge.get("retrieval_mode") or diagnostics.get("actual_retrieval_mode") or "keyword")
        vector_backend = str(knowledge.get("vector_backend") or diagnostics.get("vector_backend") or "unavailable")
        if vector_available and retrieval_mode in {"hybrid", "vector"}:
            duplicate_check_mode = retrieval_mode
        elif diagnostics.get("fallback_reason") or knowledge.get("vector_fallback_used"):
            duplicate_check_mode = "keyword_fallback"
        else:
            duplicate_check_mode = "keyword"
        scores = [float(item.get("score") or 0) for item in references if isinstance(item, dict)]
        return {
            "has_similar_knowledge": bool(references),
            "similar_references": references[:5],
            "max_similarity": max(scores) if scores else 0.0,
            "duplicate_check_mode": duplicate_check_mode,
            "vector_backend": vector_backend,
            "vector_available": vector_available,
            "fallback_reason": diagnostics.get("fallback_reason"),
            "review_note": "Similar approved knowledge was found; expert must confirm duplication risk."
            if references
            else "No similar knowledge reference was returned by the current search.",
        }

    @staticmethod
    def _extract_source_summaries(source_context: dict[str, Any]) -> dict[str, Any]:
        extracted: dict[str, Any] = {}
        for artifact in source_context.get("artifacts", []):
            artifact_type = artifact.get("artifact_type")
            content = artifact.get("content_json") or {}
            if artifact_type == "diagnosis_summary":
                extracted["diagnosis_summary"] = (
                    content.get("symptom_summary") or content.get("diagnosis_trace_id") or artifact.get("content_text")
                )
                extracted["root_cause_candidates"] = content.get("possible_causes") or []
                extracted["inspection_process"] = content.get("inspection_steps") or []
            elif artifact_type == "sop_draft":
                extracted["inspection_process"] = extracted.get("inspection_process") or content.get("steps") or []
            elif artifact_type == "task_draft":
                extracted["solution_summary"] = content.get("description") or artifact.get("content_text") or ""
        return extracted

    @staticmethod
    def _evidence_boundary(results: dict[str, AgentToolResult], source_context: dict[str, Any]) -> dict[str, bool]:
        def contains_key(value: Any, key: str, target: Any = True) -> bool:
            if isinstance(value, dict):
                if value.get(key) == target:
                    return True
                return any(contains_key(item, key, target) for item in value.values())
            if isinstance(value, list):
                return any(contains_key(item, key, target) for item in value)
            return False

        mocked = any(WorkflowAgentOrchestrator.is_mocked(result) for result in results.values())
        unreviewed_ai = False
        for artifact in source_context.get("artifacts", []):
            content = artifact.get("content_json") or {}
            mocked = mocked or contains_key(content, "mocked", True) or contains_key(content, "mocked_evidence_used", True)
            status_text = str(content).lower()
            if "pending_review" in status_text or "unreviewed" in status_text:
                unreviewed_ai = True
        media = WorkflowAgentOrchestrator.result_data(results, "media_lookup")
        for summary in (media.get("multimodal_summaries") or {}).values():
            if isinstance(summary, dict) and summary.get("latest_analysis_status") not in {None, "accepted", "approved"}:
                unreviewed_ai = True
        return {"mocked_evidence_used": mocked, "unreviewed_ai_evidence_used": unreviewed_ai}

    @staticmethod
    def _limitations(source_context: dict[str, Any], results: dict[str, AgentToolResult]) -> list[str]:
        limitations = list(source_context.get("limitations") or [])
        limitations.extend(WorkflowAgentOrchestrator.tool_warnings(results))
        limitations.append("This run creates draft artifacts only; formal knowledge conversion is reserved for Task 22J.")
        return list(dict.fromkeys([item for item in limitations if item]))

    @staticmethod
    def _source_artifact_ids_by_type(source_context: dict[str, Any], artifact_type: str) -> list[str]:
        return [
            item.get("id")
            for item in source_context.get("artifacts", [])
            if item.get("artifact_type") == artifact_type and item.get("id")
        ]

    @staticmethod
    def _source_trace_ids(source_context: dict[str, Any]) -> list[str]:
        trace_ids: list[str] = []
        for artifact in source_context.get("artifacts", []):
            content = artifact.get("content_json") or {}
            trace_id = content.get("diagnosis_trace_id") or content.get("trace_id")
            if trace_id:
                trace_ids.append(str(trace_id))
        return list(dict.fromkeys(trace_ids))

    @staticmethod
    def _quality_score(results: dict[str, AgentToolResult], source_context: dict[str, Any]) -> float:
        score = 0.35
        score += min(0.20, 0.04 * len(source_context.get("artifacts") or []))
        score += min(0.20, 0.03 * sum(1 for result in results.values() if result.status in {"succeeded", "waiting_approval"}))
        score -= min(0.15, 0.03 * sum(1 for result in results.values() if result.status in {"blocked", "failed"}))
        return round(max(0.20, min(0.82, score)), 4)

    @staticmethod
    def _confidence(results: dict[str, AgentToolResult], artifacts: list[AgentArtifact]) -> float:
        succeeded = sum(1 for result in results.values() if result.status in {"succeeded", "waiting_approval"})
        blocked = sum(1 for result in results.values() if result.status == "blocked")
        return max(0.25, min(0.80, 0.30 + 0.05 * succeeded + 0.02 * len(artifacts) - 0.03 * blocked))

    def _final_answer(
        self,
        payload: AgentRunCreateRequest,
        results: dict[str, AgentToolResult],
        artifacts: list[AgentArtifact],
        source_context: dict[str, Any],
    ) -> str:
        blocked = [name for name, result in results.items() if result.status == "blocked"]
        failed = [name for name, result in results.items() if result.status == "failed"]
        boundary = self._evidence_boundary(results, source_context)
        lines = [
            "知识沉淀智能体已生成知识贡献草稿，等待专家审核，尚未入库。",
            f"输入摘要：{(payload.input_text or '')[:260]}",
            f"生成 artifact：{', '.join(item.artifact_type for item in artifacts)}。",
            f"Blocked 工具：{', '.join(blocked) if blocked else '无'}；Failed 工具：{', '.join(failed) if failed else '无'}。",
            "本次只生成 maintenance_case_summary、knowledge_contribution_draft、kg_candidate_suggestion、safety_checklist 和 evidence_trace_summary。",
            "本次未创建正式 knowledge_contribution、knowledge_document、approved chunks、KG 节点或 KG 边。",
            "审批通过只改变 agent_approvals 状态；草稿转正式业务对象保留到 Task 22J。",
            "诊断建议和知识草稿不是最终维修结论，必须由 expert/admin 结合现场和厂家手册复核。",
            "本次未调用真实外部 API、云端模型、本地模型、OCR、Neo4j、Docker 或 SQLite；如启用向量检索，仅使用 DashVector 索引元数据和明确标记的 embedding 模式。",
        ]
        if boundary["mocked_evidence_used"]:
            lines.append("草稿包含 mock 证据，不可直接转入正式知识库。")
        if boundary["unreviewed_ai_evidence_used"]:
            lines.append("草稿包含未人工确认的 AI/图像证据，必须人工复核。")
        return "\n".join(lines)
