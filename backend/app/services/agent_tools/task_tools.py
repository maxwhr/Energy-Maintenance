from __future__ import annotations

from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool, json_safe


class TaskDraftCreatorTool(BaseAgentTool):
    tool_name = "task_draft_creator"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        text = self.text(payload, "fault_description", "input_text", "question", default="PV inverter maintenance task")
        title = self.text(payload, "title", default=f"Maintenance task draft - {text[:48]}")
        draft = {
            "title": title[:180],
            "device_id": str(context.device_id) if context.device_id else None,
            "manufacturer": payload.get("manufacturer") or context.context.get("manufacturer"),
            "product_series": payload.get("product_series") or context.context.get("product_series"),
            "device_type": payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            "fault_type": payload.get("fault_type") or context.context.get("fault_type") or "unknown",
            "alarm_code": payload.get("alarm_code") or context.context.get("alarm_code"),
            "fault_description": text,
            "description": payload.get("description") or text,
            "priority": payload.get("priority") or "medium",
            "task_status": "draft_pending_human_approval",
            "assignee": payload.get("assignee"),
            "suggested_assignee_id": payload.get("suggested_assignee_id") or context.context.get("suggested_assignee_id"),
            "suggested_due_time": payload.get("suggested_due_time") or context.context.get("suggested_due_time"),
            "safety_notes": payload.get("safety_notes") or [],
            "source_agent_run_id": context.run_id,
            "source_artifact_ids": payload.get("source_artifact_ids") or [],
            "requires_approval": True,
            "dry_run": True,
            "formal_task_created": False,
            "created_by_agent_run": context.run_id,
        }
        return AgentToolResult(
            tool_name=self.tool_name,
            status="waiting_approval",
            summary="Maintenance task draft prepared; no formal task was created.",
            data={"task_draft": json_safe(draft)},
            requires_approval=True,
        )
