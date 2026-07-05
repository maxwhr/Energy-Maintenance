from __future__ import annotations

from app.schemas.diagnosis import DiagnosisAnalyzeRequest
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool
from app.services.diagnosis_service import DiagnosisService


FAULT_TYPE_ALIASES = {
    "insulation_low": "low_insulation_resistance",
    "low_insulation": "low_insulation_resistance",
    "overtemperature": "over_temperature",
    "communication_fault": "communication_interruption",
    "grid_fault": "grid_connection_fault",
    "mppt_low_power": "low_power_generation",
}


class DiagnosisRuleEngineTool(BaseAgentTool):
    tool_name = "diagnosis_rule_engine"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        fault_description = self.text(payload, "fault_description", "input_text", "question")
        if not fault_description:
            return AgentToolResult(
                tool_name=self.tool_name,
                status="blocked",
                summary="diagnosis_rule_engine requires a fault description.",
                blocked_reason="empty_fault_description",
            )
        request = DiagnosisAnalyzeRequest(
            device_id=context.device_id,
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            model=payload.get("model") or context.context.get("model"),
            device_type=payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            fault_type=self._fault_type(payload.get("fault_type") or context.context.get("fault_type")),
            alarm_code=payload.get("alarm_code") or context.context.get("alarm_code"),
            fault_description=fault_description,
            observed_symptoms=payload.get("observed_symptoms") or [],
            media_ids=context.media_ids,
            use_ocr_text=bool(payload.get("use_ocr_text", False)),
            enable_model_enhancement=False,
            model_provider="rule_based",
        )
        result = DiagnosisService(context.db).analyze(request, context.current_user)
        output = result.model_dump(mode="json")
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Rule-based diagnosis completed with trace_id={output.get('trace_id')}.",
            data=output,
            evidence=output.get("references", []),
        )

    @staticmethod
    def _fault_type(value: str | None) -> str:
        if not value:
            return "unknown"
        return FAULT_TYPE_ALIASES.get(value, value)
