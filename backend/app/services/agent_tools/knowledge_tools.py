from __future__ import annotations

from app.schemas.retrieval import RetrievalQueryRequest
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool, json_safe
from app.services.retrieval_service import RetrievalService


class KnowledgeSearchTool(BaseAgentTool):
    tool_name = "knowledge_search"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        query = self.text(payload, "query", "question", "input_text")
        if not query:
            return AgentToolResult(
                tool_name=self.tool_name,
                status="blocked",
                summary="knowledge_search requires a non-empty question.",
                blocked_reason="empty_query",
            )
        top_k = self.bounded_int(payload.get("top_k"), default=5, minimum=1, maximum=10)
        request = RetrievalQueryRequest(
            query=query,
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            device_type=payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            device_id=context.device_id,
            document_type=payload.get("document_type") or context.context.get("document_type"),
            fault_type=payload.get("fault_type") or context.context.get("fault_type"),
            alarm_code=payload.get("alarm_code") or context.context.get("alarm_code"),
            media_ids=context.media_ids,
            use_ocr_text=bool(payload.get("use_ocr_text", False)),
            top_k=top_k,
            enable_model_enhancement=False,
            model_provider="rule_based",
        )
        result = RetrievalService(context.db).query(request, context.current_user)
        output = result.model_dump(mode="json")
        references = output.get("references", [])
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Retrieved {len(output.get('retrieved_chunks', []))} knowledge chunks.",
            data=output,
            evidence=references,
        )


class KnowledgeContributionDraftCreatorTool(BaseAgentTool):
    tool_name = "knowledge_contribution_draft_creator"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        title = self.text(payload, "title", default="PV inverter maintenance knowledge contribution draft")
        content = self.text(payload, "content", "input_text", "question", default="No draft content provided.")
        case_summary = payload.get("maintenance_case_summary") if isinstance(payload.get("maintenance_case_summary"), dict) else {}
        duplicate_risk = payload.get("duplicate_risk") if isinstance(payload.get("duplicate_risk"), dict) else {}
        knowledge_references = payload.get("knowledge_references") if isinstance(payload.get("knowledge_references"), list) else []
        kg_context = payload.get("kg_context") if isinstance(payload.get("kg_context"), dict) else {}
        source_agent_run_ids = payload.get("source_agent_run_ids") if isinstance(payload.get("source_agent_run_ids"), list) else []
        source_artifact_ids = payload.get("source_artifact_ids") if isinstance(payload.get("source_artifact_ids"), list) else []
        related_media_ids = payload.get("related_media_ids") if isinstance(payload.get("related_media_ids"), list) else []
        troubleshooting_steps = payload.get("troubleshooting_steps") if isinstance(payload.get("troubleshooting_steps"), list) else []
        safety_precautions = payload.get("safety_precautions") if isinstance(payload.get("safety_precautions"), list) else []
        limitations = payload.get("limitations") if isinstance(payload.get("limitations"), list) else []
        draft = {
            "title": title[:180],
            "category": payload.get("category") or "maintenance_experience",
            "device_scope": {
                "manufacturer": payload.get("manufacturer") or context.context.get("manufacturer"),
                "product_series": payload.get("product_series") or context.context.get("product_series"),
                "model": payload.get("model") or case_summary.get("model"),
                "device_type": payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            },
            "fault_type": payload.get("fault_type") or context.context.get("fault_type"),
            "alarm_code": payload.get("alarm_code") or context.context.get("alarm_code"),
            "problem_description": payload.get("problem_description") or case_summary.get("symptom") or content,
            "cause_analysis": payload.get("cause_analysis") or case_summary.get("diagnosis_summary") or "",
            "troubleshooting_steps": troubleshooting_steps,
            "solution": payload.get("solution") or case_summary.get("solution_summary") or "",
            "safety_precautions": safety_precautions,
            "applicable_conditions": payload.get("applicable_conditions")
            or ["Huawei/Sungrow PV inverter maintenance scenarios with matching symptoms."],
            "not_applicable_conditions": payload.get("not_applicable_conditions")
            or ["Do not apply directly to non-PV-inverter equipment or unverified high-voltage work."],
            "related_media_ids": related_media_ids,
            "related_agent_run_ids": source_agent_run_ids,
            "related_artifact_ids": source_artifact_ids,
            "knowledge_references": knowledge_references,
            "kg_context": kg_context,
            "duplicate_risk": duplicate_risk or {"has_similar_knowledge": False, "similar_references": []},
            "mocked_evidence_used": bool(payload.get("mocked_evidence_used", False)),
            "unreviewed_ai_evidence_used": bool(payload.get("unreviewed_ai_evidence_used", False)),
            "requires_expert_review": True,
            "draft_quality_score": float(payload.get("draft_quality_score") or 0.55),
            "limitations": limitations,
            "status": "draft_pending_human_review",
            "created_by_agent_run": context.run_id,
            "dry_run": True,
            "formal_contribution_created": False,
            "formal_document_created": False,
            "approved_chunks_created": False,
        }
        return AgentToolResult(
            tool_name=self.tool_name,
            status="waiting_approval",
            summary="Knowledge contribution draft prepared; formal submission requires human approval.",
            data={"knowledge_contribution_draft": json_safe(draft)},
            requires_approval=True,
        )
