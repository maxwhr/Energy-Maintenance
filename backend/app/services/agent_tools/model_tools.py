from __future__ import annotations

from app.schemas.model_gateway import ModelGatewayChatRequest
from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool
from app.services.external_api_gateway import ExternalApiGateway, ExternalApiGatewayError
from app.services.model_gateway_service import ModelGatewayService


class ModelGatewayChatTool(BaseAgentTool):
    tool_name = "model_gateway_chat"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        prompt = self.text(payload, "prompt", "input_text", "question")
        if not prompt:
            return AgentToolResult(
                tool_name=self.tool_name,
                status="blocked",
                summary="model_gateway_chat requires a non-empty prompt.",
                blocked_reason="empty_prompt",
            )
        requested_provider = str(payload.get("provider") or "").strip()
        if requested_provider not in {"rule_based", "local_llama_cpp", "cloud_openai"}:
            requested_provider = "rule_based"
        if requested_provider != "rule_based" and not (
            payload.get("real_run") is True and context.current_user.role in {"admin", "expert"}
        ):
            requested_provider = "rule_based"
        request = ModelGatewayChatRequest(
            prompt=prompt,
            provider=requested_provider,
            task_type=payload.get("task_type") or "general",
            allow_fallback=True,
            trace_source=f"agent_run:{context.run_id}",
        )
        result = ModelGatewayService(context.db).chat(request, context.current_user)
        output = result.model_dump(mode="json")
        try:
            gateway_result = ExternalApiGateway(context.db).dry_run_for_tool(
                tool_name=self.tool_name,
                capability="text_chat",
                current_user=context.current_user,
                agent_code=context.context.get("agent_code"),
                agent_run_id=context.run_id,
                input_summary={
                    "prompt_preview": prompt[:160],
                    "prompt_length": len(prompt),
                    "task_type": payload.get("task_type") or "general",
                    "model_gateway_provider": output.get("provider"),
                    "model_gateway_trace_id": output.get("trace_id"),
                },
            ).model_dump(mode="json")
        except ExternalApiGatewayError as exc:
            gateway_result = {
                "status": "blocked",
                "provider_code": None,
                "blocked_reason": "external_api_route_unavailable",
                "message": str(exc),
                "external_api_called": False,
            }
        output["external_api_gateway"] = gateway_result
        output["external_api_called"] = bool(output.get("provider") == "cloud_openai" and output.get("success"))
        output["provider_mode"] = (
            "real"
            if output.get("provider") == "cloud_openai" and output.get("success") and not output.get("fallback_used")
            else "fallback"
            if output.get("fallback_used")
            else "rule_based"
            if output.get("provider") == "rule_based"
            else "blocked"
        )
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded" if output.get("success") else "blocked",
            summary=f"Model gateway returned provider={output.get('provider')} trace_id={output.get('trace_id')}.",
            data=output,
        )


class CorrectionSubmitterTool(BaseAgentTool):
    tool_name = "correction_submitter"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        correction = {
            "source_trace_id": payload.get("trace_id") or context.context.get("trace_id"),
            "original_text": payload.get("original_text") or payload.get("input_text"),
            "corrected_text": payload.get("corrected_text") or "",
            "reason": payload.get("reason") or "Agent-prepared correction draft.",
            "dry_run": True,
            "formal_correction_created": False,
            "created_by_agent_run": context.run_id,
        }
        return AgentToolResult(
            tool_name=self.tool_name,
            status="waiting_approval",
            summary="Correction draft prepared; formal correction submission requires human approval.",
            data={"correction_draft": correction},
            requires_approval=True,
        )
