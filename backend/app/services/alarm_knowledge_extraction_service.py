from __future__ import annotations

import re
from typing import Any


class AlarmKnowledgeExtractionService:
    """Extract explicit codes and named fault knowledge without inventing identifiers."""

    EXPLICIT_CONTEXT = re.compile(
        r"(?i)(?:alarm|fault|告警|故障)(?:\s*(?:id|code|码|编号))?\s*[:#：-]?\s*([A-Z]{0,5}[-_]?\d{3,6})\b"
    )
    HEADING_CODE = re.compile(r"^\s*(\d{3,6}|[A-Z]{1,5}[-_]\d{2,6})\s+(.{3,160})$", re.I)
    HEADING_CODE_MULTILINE = re.compile(
        r"(?im)^#{0,3}\s*(\d{3,6}|[A-Z]{1,5}[-_]\d{2,6})\s+([^\r\n#]{3,160})$"
    )
    NAMED_ALARM = re.compile(
        r"(?i)(?:alarm|fault|failure|fails?|unable|abnormal|low yield|red indicator|"
        r"告警|故障|失败|异常|不开机|红灯|发电量低|绝缘阻抗低|过温|接地|离线|中断)"
    )
    SAFETY = re.compile(
        r"(?i)(?:power off|shut down|disconnect|turn off|qualified personnel|PPE|insulated tools|"
        r"断电|停机|关闭|专业人员|绝缘工具|防护|警告|危险|安全)"
    )
    STEP = re.compile(r"(?im)^(?:step\s*\d+|步骤\s*\d+|\d+[.)、]\s+)")

    def extract(
        self,
        *,
        title: str,
        text: str,
        device_models: list[str] | None = None,
        source_locator: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        explicit = set(self.EXPLICIT_CONTEXT.findall(text))
        coded_headings = self.HEADING_CODE_MULTILINE.findall(text)
        explicit.update(code for code, _ in coded_headings)
        heading_match = self.HEADING_CODE.match(title.strip())
        named: list[dict[str, Any]] = []
        if heading_match:
            explicit.add(heading_match.group(1))
            alarm_name = heading_match.group(2).strip(" -:")
            if self.NAMED_ALARM.search(alarm_name):
                named.append(self._named(alarm_name, device_models, source_locator))
        if self.NAMED_ALARM.search(title) and not named:
            named.append(self._named(title.strip(), device_models, source_locator))
        for _, alarm_name in coded_headings:
            cleaned = alarm_name.strip(" -:")
            if cleaned and not any(item["alarm_name"] == cleaned for item in named):
                named.append(self._named(cleaned, device_models, source_locator))
        fault_symptoms = [title.strip()] if self.NAMED_ALARM.search(title) else []
        return {
            "explicit_alarm_codes": sorted(explicit),
            "named_alarms": named,
            "fault_symptoms": fault_symptoms,
            "troubleshooting_steps": len(self.STEP.findall(text)),
            "safety_actions": len(self.SAFETY.findall(text)),
        }

    @staticmethod
    def _named(name: str, models: list[str] | None, locator: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "alarm_identifier": name,
            "alarm_identifier_type": "name_only",
            "alarm_name": name,
            "applicable_device_models": models or [],
            "source_locator": locator or {},
        }
