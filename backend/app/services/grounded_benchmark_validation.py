from __future__ import annotations

import re


def ngrams(value: str) -> set[str]:
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.lower())
    return {
        normalized[index:index + width]
        for width in (2, 3)
        for index in range(max(0, len(normalized) - width + 1))
    }


def overlap(left: str, right: str) -> float:
    a, b = ngrams(left), ngrams(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def topic_hint(unit: dict) -> str:
    section = re.sub(r"^\s*[\d.]+\s*", "", str(unit.get("source_section") or "")).strip()
    for value in [*(unit.get("device_models") or []), *(unit.get("alarm_codes") or [])]:
        if value:
            section = section.replace(str(value), " ")
    candidates = [
        value for value in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,12}", section)
        if value.lower() not in {"sun2000", "luna2000", "smartlogger", "fusionsolar"}
    ]
    generic = ("设置", "操作", "处理", "故障", "告警", "检查", "安装", "维护", "步骤", "说明", "配置", "更换", "调试")
    for value in candidates:
        reduced = value
        for term in generic:
            reduced = reduced.replace(term, "")
        reduced = reduced.strip()
        if len(reduced) >= 2 and reduced.lower() != section.lower():
            return reduced[:12]
    source_tail = section.strip(" \t\r\n，。；：、（）()[]【】")
    if len(source_tail) >= 5:
        return source_tail[-min(8, len(source_tail) - 1):].lstrip("，。；：、（）()[]【】")
    return ""


def grounded_query(unit: dict) -> tuple[str, list[str]]:
    hint = topic_hint(unit)
    concepts = list(dict.fromkeys([
        hint,
        *unit["component_terms"][:1], *unit["symptom_terms"][:1], *unit["cause_terms"][:1],
        *unit["action_terms"][:1], *unit["safety_terms"][:1], *unit["prerequisite_terms"][:1],
        *unit["verification_terms"][:1],
    ]))
    focus = "、".join(value for value in concepts[:4] if value) or "设备状态"
    templates = {
        "COMMUNICATION": f"现场出现{focus}相关异常时，应从哪些通信条件和处理动作开始排查？",
        "ALARM": f"设备出现{focus}相关现象但没有完整告警标识时，应如何判断并处理？",
        "PROCEDURE": f"进行{focus}相关检修时，操作前、操作中和完成后分别要确认什么？",
        "SAFETY": f"处理{focus}相关问题前，需要落实哪些风险隔离和安全措施？",
        "CAUSE": f"出现{focus}相关现象时，资料给出的原因线索与检查动作是什么？",
        "SYMPTOM": f"现场表现为{focus}时，应该优先核查哪些条件并采取什么动作？",
        "ACTION": f"面对{focus}相关问题，现场应按什么顺序检查和处理？",
    }
    return templates.get(unit["semantic_unit_type"], f"针对{focus}相关问题，资料给出的检修要点是什么？"), concepts[:4]
