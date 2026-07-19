from __future__ import annotations

from typing import Any


class MultimodalClarificationService:
    TEMPLATES = {
        "device_model": ("DEVICE_MODEL", "请补充设备完整型号，或重新拍摄清晰且完整的铭牌。"),
        "alarm_code_or_symptom": ("ALARM_CODE", "请补充屏幕上的完整告警代码；如无代码，请描述可见故障现象。"),
        "conflict_resolution": ("CONFLICT", "检测到证据不一致，请确认哪项信息对应当前故障设备。"),
        "blurry_image": ("IMAGE_QUALITY", "图片较模糊，请重新拍摄清晰的铭牌或完整屏幕。"),
        "screen_incomplete": ("SCREEN_REGION", "请拍摄完整屏幕而非局部区域。"),
        "indicator_mode": ("INDICATOR_STATE", "请说明指示灯颜色，以及常亮、闪烁或熄灭状态。"),
        "occurrence_condition": ("OCCURRENCE", "请说明问题发生在上电、并网、升级后、夜间或其他条件下。"),
        "current_device": ("MEDIA_OWNERSHIP", "请确认图片是否为当前故障设备。"),
    }

    def build(
        self,
        *,
        missing_information: list[str],
        conflicts: list[dict[str, Any]],
        image_quality_flags: list[str] | None = None,
        needs_ocr: bool = False,
    ) -> list[dict[str, Any]]:
        keys = list(missing_information)
        if conflicts and "conflict_resolution" not in keys:
            keys.append("conflict_resolution")
        flags = set(image_quality_flags or [])
        if flags.intersection({"possibly_blurry", "too_small", "very_low_contrast"}):
            keys.append("blurry_image")
        if needs_ocr:
            keys.append("screen_incomplete")
        result = []
        for key in dict.fromkeys(keys):
            template = self.TEMPLATES.get(key)
            if not template:
                continue
            question_type, question = template
            result.append({
                "question_id": f"mmq_{key}",
                "question_type": question_type,
                "question": question,
                "required": key in {"device_model", "conflict_resolution"},
                "safe_template": True,
            })
        return result[:8]
