from __future__ import annotations

import re

from app.schemas.query_understanding import QueryUnderstandingResult
from app.schemas.retrieval_plan import RetrievalQueryVariant


class DeterministicQueryExpansionService:
    """Planner V3 query variants: bounded, source-independent and deterministic."""

    VERSION = "task25b_r3_dev_r5_r5_planner_v3"
    REQUEST_TERMS = {
        "CAUSE": "可能原因",
        "ACTION": "排查和处理方法",
        "PROCEDURE": "操作步骤",
        "SAFETY": "安全要求",
        "ALARM_MEANING": "告警含义",
        "PREREQUISITE": "操作前条件",
        "VERIFICATION": "完成后确认方法",
        "CONFIGURATION": "配置参数和设置方法",
        "GENERAL_INFORMATION": "相关信息",
    }

    def expand(self, understanding: QueryUnderstandingResult) -> list[RetrievalQueryVariant]:
        candidates = [
            RetrievalQueryVariant(
                variant_type="ORIGINAL", query=understanding.original_query,
                hypothesis=False, purpose="retain the user's exact expression",
            ),
        ]
        canonical = understanding.canonical_question.strip()
        if canonical:
            candidates.append(RetrievalQueryVariant(
                variant_type="CANONICAL", query=canonical,
                hypothesis=False, purpose="normalized wording without new entities",
            ))
        symptom = self._symptom_query(understanding)
        if symptom:
            candidates.append(RetrievalQueryVariant(
                variant_type="SYMPTOM_QUERY", query=symptom,
                hypothesis=True, purpose="focus confirmed symptom or alarm",
            ))
        request = self._request_query(understanding)
        if request:
            candidates.append(RetrievalQueryVariant(
                variant_type="REQUEST_QUERY", query=request,
                hypothesis=False, purpose="cover every explicitly requested information type",
            ))
        condition = self._condition_query(understanding)
        if condition:
            candidates.append(RetrievalQueryVariant(
                variant_type="CONDITION_QUERY", query=condition,
                hypothesis=True, purpose="preserve confirmed operating conditions",
            ))
        unique: list[RetrievalQueryVariant] = []
        seen: set[str] = set()
        for item in candidates:
            key = re.sub(r"\s+", "", item.query).strip("，。；：？！").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique[:5]

    def _symptom_query(self, understanding: QueryUnderstandingResult) -> str:
        entities = [*understanding.device_models, *understanding.alarm_codes, *understanding.alarm_names]
        focus = [*understanding.symptoms, *understanding.components]
        values = list(dict.fromkeys([*entities, *focus]))[:4]
        return " ".join(values)

    def _request_query(self, understanding: QueryUnderstandingResult) -> str:
        requested = [self.REQUEST_TERMS[value] for value in understanding.requested_information if value in self.REQUEST_TERMS]
        requested = list(dict.fromkeys(requested))[:5]
        if not requested:
            return ""
        subject = self._subject(understanding)
        return f"{subject} {'；'.join(requested)}".strip()

    def _condition_query(self, understanding: QueryUnderstandingResult) -> str:
        conditions = list(dict.fromkeys(understanding.conditions))[:3]
        if not conditions:
            return ""
        return f"{' '.join(conditions)} {self._subject(understanding)}".strip()

    @staticmethod
    def _subject(understanding: QueryUnderstandingResult) -> str:
        explicit = [
            *understanding.device_models, *understanding.alarm_codes, *understanding.alarm_names,
            *understanding.symptoms, *understanding.components,
        ]
        explicit = list(dict.fromkeys(value for value in explicit if value))[:4]
        if explicit:
            return " ".join(explicit)
        if understanding.primary_intent == "COMMUNICATION":
            return "通信异常"
        return "设备问题"
