from __future__ import annotations

from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool, json_safe
from app.services.knowledge_graph_service import KnowledgeGraphService


class KGBusinessContextTool(BaseAgentTool):
    tool_name = "kg_business_context"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        question = self.text(payload, "question", "query", "input_text")
        result = KnowledgeGraphService(context.db).business_context(
            current_user=context.current_user,
            device_id=context.device_id,
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            fault_type=payload.get("fault_type") or context.context.get("fault_type"),
            alarm_code=payload.get("alarm_code") or context.context.get("alarm_code"),
            question=question,
            limit=self.bounded_int(payload.get("limit"), default=30, minimum=1, maximum=80),
        )
        summary = result.get("summary") or {}
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=(
                "Knowledge graph context resolved "
                f"nodes={summary.get('matched_node_count', 0)} edges={summary.get('edge_count', 0)}."
            ),
            data=json_safe(result),
            evidence=json_safe(result.get("evidence", [])),
        )
