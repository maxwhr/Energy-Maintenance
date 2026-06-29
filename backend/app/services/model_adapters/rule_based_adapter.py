from __future__ import annotations

import re
import time

from app.schemas.model_gateway import ModelProviderStatus
from app.services.model_adapters.base import ModelAdapterRequest, ModelAdapterResponse


class RuleBasedAdapter:
    provider = "rule_based"
    model_name = "rule_based_fallback_v1"

    def status(self) -> ModelProviderStatus:
        return ModelProviderStatus(
            provider=self.provider,
            enabled=True,
            configured=True,
            available=True,
            availability_status="available",
            model_name=self.model_name,
            message="Rule-based fallback is available without external model service.",
        )

    def chat(self, request: ModelAdapterRequest) -> ModelAdapterResponse:
        started_at = time.perf_counter()
        content = self._build_response(request)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return ModelAdapterResponse(
            provider=self.provider,
            model_name=self.model_name,
            content=content,
            success=True,
            latency_ms=latency_ms,
            usage={
                "prompt_chars": len(request.prompt),
                "response_chars": len(content),
            },
        )

    def _build_response(self, request: ModelAdapterRequest) -> str:
        prompt = self._compact(request.prompt)
        focus_terms = self._extract_focus_terms(prompt)
        focus_line = "、".join(focus_terms) if focus_terms else "告警现象、设备状态、厂家手册和现场安全条件"

        if request.task_type == "diagnosis":
            body = [
                "这是规则型诊断辅助结果，适用于华为与阳光电源光伏逆变器第一版范围。",
                f"建议优先围绕 {focus_line} 核对故障边界，确认告警码、并网状态、直流侧输入和交流侧保护动作。",
                "处理前应执行停送电和绝缘防护确认，必要时以厂家手册与现场工程师判断为准。",
            ]
        elif request.task_type == "sop":
            body = [
                "这是规则型 SOP 辅助草案，面向光伏逆变器检修作业。",
                f"建议按安全确认、现象复核、{focus_line} 检查、处理措施确认、复检归档的顺序执行。",
                "若涉及带电测量、绝缘测试或并网操作，应由具备资质的人员按站内规程执行。",
            ]
        elif request.task_type == "summary":
            body = [
                "这是规则型摘要结果，未调用外部模型。",
                f"输入内容主要涉及 {focus_line}。",
                "建议后续结合已入库的华为 SUN2000 / FusionSolar 与阳光电源 SG 系列资料进行来源追溯。",
            ]
        elif request.task_type == "correction":
            body = [
                "这是规则型修正建议，用于辅助人工审核。",
                f"请重点检查 {focus_line} 是否与原始知识片段、厂家资料和安全规程一致。",
                "修正内容应保留来源、适用厂家、产品系列和适用故障类型。",
            ]
        else:
            body = [
                "这是规则型模型网关响应，未调用真实大模型。",
                f"当前问题可先围绕 {focus_line} 做检修知识核对。",
                "系统第一版聚焦华为与阳光电源光伏逆变器，不替代现场工程师和厂家安全手册。",
            ]
        return "\n".join(body)

    @staticmethod
    def _compact(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _extract_focus_terms(text: str) -> list[str]:
        candidates = [
            "华为",
            "阳光电源",
            "SUN2000",
            "FusionSolar",
            "SG",
            "逆变器",
            "光伏",
            "告警",
            "绝缘",
            "过温",
            "并网",
            "离线",
            "风扇",
            "MPPT",
            "直流",
            "交流",
            "通信",
            "低发电量",
            "排查",
        ]
        lowered = text.lower()
        found: list[str] = []
        for item in candidates:
            if item.lower() in lowered and item not in found:
                found.append(item)
        return found[:6]
