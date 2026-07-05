from __future__ import annotations

from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool, json_safe
from app.services.device_service import DeviceService
from app.services.record_center_service import RecordCenterService, RecordCenterServiceError


class DeviceLookupTool(BaseAgentTool):
    tool_name = "device_lookup"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        service = DeviceService(context.db)
        if context.device_id:
            device = service.get_device(context.device_id)
            if not device:
                return AgentToolResult(
                    tool_name=self.tool_name,
                    status="blocked",
                    summary="Device was not found.",
                    blocked_reason="device_not_found",
                    data={"device_id": str(context.device_id)},
                )
            return AgentToolResult(
                tool_name=self.tool_name,
                status="succeeded",
                summary=f"Device resolved: {device.device_name}.",
                data={"device": json_safe(device)},
            )

        result = service.list_devices(
            manufacturer=payload.get("manufacturer") or context.context.get("manufacturer"),
            product_series=payload.get("product_series") or context.context.get("product_series"),
            device_type=payload.get("device_type") or context.context.get("device_type") or "pv_inverter",
            status=payload.get("status"),
            keyword=payload.get("keyword") or payload.get("device_code") or payload.get("device_name"),
            page=1,
            page_size=self.bounded_int(payload.get("page_size"), default=5, minimum=1, maximum=20),
        )
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Device lookup returned {len(result.get('items', []))} items.",
            data=json_safe(result),
        )


class DeviceHistoryTool(BaseAgentTool):
    tool_name = "device_history"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        if not context.device_id:
            return AgentToolResult(
                tool_name=self.tool_name,
                status="skipped",
                summary="No device_id was provided, so device history lookup was skipped.",
                data={"items": [], "device_id": None},
            )
        try:
            result = RecordCenterService(context.db).device_timeline(
                device_id=context.device_id,
                record_type=payload.get("record_type"),
                limit=self.bounded_int(payload.get("limit"), default=20, minimum=1, maximum=50),
            )
        except RecordCenterServiceError as exc:
            return AgentToolResult(
                tool_name=self.tool_name,
                status="blocked",
                summary="Device history lookup could not be completed.",
                blocked_reason=str(exc),
                data={"device_id": str(context.device_id)},
            )
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Device history returned {len(result.get('items', []))} records.",
            data=json_safe(result),
        )
