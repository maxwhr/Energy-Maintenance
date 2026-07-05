from __future__ import annotations

from app.schemas.sop import SOPGenerateRequest
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool
from app.services.sop_service import SOPService


FAULT_TYPE_ALIASES = {
    "insulation_low": "low_insulation_resistance",
    "low_insulation": "low_insulation_resistance",
    "overtemperature": "over_temperature",
    "communication_fault": "communication_interruption",
    "grid_fault": "grid_connection_fault",
    "mppt_low_power": "low_power_generation",
}


class SOPGeneratorTool(BaseAgentTool):
    tool_name = "sop_generator"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        request = SOPGenerateRequest(
            device_id=context.device_id,
            diagnosis_trace_id=payload.get("diagnosis_trace_id") or context.context.get("diagnosis_trace_id"),
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            model=payload.get("model") or context.context.get("model"),
            device_type=payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            fault_type=self._fault_type(payload.get("fault_type") or context.context.get("fault_type")),
            alarm_code=payload.get("alarm_code") or context.context.get("alarm_code"),
            maintenance_level=payload.get("maintenance_level") or "level_2",
            include_references=True,
            enable_model_enhancement=False,
            model_provider="rule_based",
        )
        result = SOPService(context.db).generate(request, context.current_user)
        output = result.model_dump(mode="json")
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"SOP draft generated with {len(output.get('steps', []))} steps.",
            data=output,
            evidence=output.get("references", []),
        )

    @staticmethod
    def _fault_type(value: str | None) -> str:
        if not value:
            return "unknown"
        return FAULT_TYPE_ALIASES.get(value, value)
