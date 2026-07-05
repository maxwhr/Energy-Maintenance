from __future__ import annotations

from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool, json_safe
from app.services.record_center_service import RecordCenterService


class RecordCenterLookupTool(BaseAgentTool):
    tool_name = "record_center_lookup"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        result = RecordCenterService(context.db).search(
            record_type=payload.get("record_type") or "all",
            device_id=context.device_id,
            keyword=payload.get("keyword") or self.text(payload, "query", "question", "input_text", default=None),
            trace_id=payload.get("trace_id"),
            status=payload.get("status"),
            fault_type=payload.get("fault_type") or context.context.get("fault_type"),
            alarm_code=payload.get("alarm_code") or context.context.get("alarm_code"),
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            page=1,
            page_size=self.bounded_int(payload.get("page_size"), default=10, minimum=1, maximum=50),
        )
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Record center lookup returned {len(result.get('items', []))} items.",
            data=json_safe(result),
        )
