from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.schemas.query_understanding import QueryUnderstandingResult


@dataclass(frozen=True, slots=True)
class RerankQuery:
    text: str
    text_hash: str


class RerankQueryBuilder:
    def build(self, understanding: QueryUnderstandingResult) -> RerankQuery:
        confirmed = understanding.confirmed_facts or {}
        communication = confirmed.get("communication_terms") or confirmed.get("communication_method") or []
        if isinstance(communication, str):
            communication = [communication]
        lines = [
            f"原始查询：{understanding.original_query}",
            f"规范查询：{understanding.canonical_question}",
            f"主要意图：{understanding.primary_intent}",
            f"请求信息：{'；'.join(understanding.requested_information)}",
            f"确认型号：{'；'.join(understanding.device_models)}",
            f"确认告警：{'；'.join([*understanding.alarm_codes, *understanding.alarm_names])}",
            f"发生条件：{'；'.join(understanding.conditions)}",
            f"通信条件：{'；'.join(str(value) for value in communication)}",
        ]
        text = "\n".join(line for line in lines if not line.endswith("："))
        return RerankQuery(text=text, text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest())
