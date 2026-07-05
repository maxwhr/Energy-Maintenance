from __future__ import annotations

from app.services.agent_tools.base import AgentToolExecutionContext, AgentToolResult, BaseAgentTool


SAFETY_KEYWORDS = {
    "insulation": "存在绝缘相关线索时，应先确认组串绝缘电阻、接地状态和柜体潮湿情况。",
    "low_insulation": "绝缘阻抗偏低场景应升级复核，严禁带电开柜直接处理。",
    "over_temperature": "过温场景应等待温度回落，检查风扇、风道和散热器前必须确认无电压。",
    "fan": "风扇异常排查前需确认风扇停转、直流侧和交流侧均已隔离。",
    "dc": "直流侧检查前必须确认 DC 开关状态、组串电压和残余电荷。",
    "ac": "交流侧检查前必须确认并网侧隔离、残余电压和防反送电措施。",
    "alarm": "告警代码必须与华为/阳光电源厂家手册交叉核对，不能仅凭图片或文本判断。",
    "communication": "通信中断排查不得影响并网安全，先确认设备运行状态和告警等级。",
    "offline": "离线设备恢复通信前，应先确认设备本体是否处于故障或停机状态。",
}


class SafetyGuardTool(BaseAgentTool):
    tool_name = "safety_guard"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        text = " ".join(
            str(payload.get(key) or context.context.get(key) or "")
            for key in ["input_text", "question", "fault_description", "fault_type", "alarm_code"]
        ).lower()
        must_do = [
            "断开直流侧和交流侧电源，并执行挂牌上锁。",
            "使用合格验电器确认无电压，等待厂家规定的放电时间。",
            "佩戴绝缘手套、绝缘鞋、护目镜等绝缘防护用品。",
            "至少两名具备资质的现场人员进行双人复核，确认告警、隔离点和作业步骤一致。",
        ]
        warnings = [
            "本安全清单不能替代现场工程师判断或华为/阳光电源厂家安全手册。",
            "未完成断电、验电、放电确认前，不得打开逆变器柜门或触碰端子。",
        ]
        notices = [
            "记录 trace_id、媒体证据、工具调用结果和现场复核结论。",
            "机器 OCR / 图像分析仅作为辅助证据，正式作业前必须人工复核。",
        ]
        risk_level = "medium"
        for keyword, note in SAFETY_KEYWORDS.items():
            if keyword in text and note not in warnings:
                warnings.append(note)
        if any(keyword in text for keyword in ["insulation", "low_insulation", "over_temperature", "short", "burn", "smoke", "绝缘", "过温", "短路", "烧蚀", "冒烟"]):
            risk_level = "high"
        return AgentToolResult(
            tool_name=self.tool_name,
            status="succeeded",
            summary=f"Safety guard produced {len(must_do) + len(warnings)} PV inverter safety checklist items.",
            data={
                "must_do": must_do,
                "risk_level": risk_level,
                "warnings": warnings,
                "notices": notices,
                "safety_notes": [*must_do, *warnings, *notices],
                "requires_field_engineer_confirmation": True,
                "external_api_called": False,
            },
        )


class HumanApprovalTool(BaseAgentTool):
    tool_name = "human_approval"

    def execute(self, payload: dict, context: AgentToolExecutionContext) -> AgentToolResult:
        return AgentToolResult(
            tool_name=self.tool_name,
            status="waiting_approval",
            summary="Human approval is required before high-risk write actions are finalized.",
            data={"approval_required": True, "formal_write_executed": False},
            requires_approval=True,
        )
