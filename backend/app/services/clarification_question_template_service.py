from __future__ import annotations

from app.schemas.query_understanding import MissingSlotV2


class ClarificationQuestionTemplateService:
    """Generate bounded clarification text without a model-owned free-text field."""

    PRIORITY: tuple[MissingSlotV2, ...] = (
        "SPECIFIC_SYMPTOM",
        "ALARM_CODE",
        "REQUESTED_ACTION",
        "COMMUNICATION_METHOD",
        "DEVICE_MODEL",
        "COMPONENT",
        "OCCURRENCE_CONDITION",
    )
    TEMPLATES: dict[MissingSlotV2, str] = {
        "DEVICE_MODEL": "请补充设备型号。",
        "ALARM_CODE": "请补充设备显示的告警代码或告警名称。",
        "SPECIFIC_SYMPTOM": "请说明具体表现是不发电、无法上电、指示灯异常，还是平台连接不上。",
        "COMPONENT": "请说明出现异常的具体部件。",
        "COMMUNICATION_METHOD": "请说明使用的是 WiFi、4G、以太网还是 RS485 通信。",
        "OCCURRENCE_CONDITION": "请说明异常发生的时间、运行状态或触发条件。",
        "REQUESTED_ACTION": "请说明您要查询原因、排查方法、操作步骤、安全要求，还是恢复验证。",
    }

    def questions(self, missing_slots: list[MissingSlotV2], *, limit: int = 3) -> list[str]:
        requested = set(missing_slots)
        bounded = max(1, min(3, int(limit)))
        return [self.TEMPLATES[slot] for slot in self.PRIORITY if slot in requested][:bounded]

    def first(self, missing_slots: list[MissingSlotV2]) -> str | None:
        questions = self.questions(missing_slots, limit=1)
        return questions[0] if questions else None
