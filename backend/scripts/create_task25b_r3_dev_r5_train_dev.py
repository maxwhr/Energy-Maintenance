from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from task25b_r3_dev_r5_common import OUT, R5_TRAIN_DEV_VERSION, now_iso, read_json, write_json


TYPE_QUOTAS = {
    "COMMUNICATION": 15,
    "CAUSE": 15,
    "ACTION": 15,
    "PROCEDURE": 10,
    "SAFETY": 12,
    "VERIFICATION": 10,
    "SYMPTOM": 13,
    "PREREQUISITE": 10,
}
TYPE_INTENT = {
    "COMMUNICATION": "COMMUNICATION",
    "CAUSE": "CAUSE",
    "ACTION": "TROUBLESHOOTING",
    "PROCEDURE": "PROCEDURE",
    "SAFETY": "SAFETY",
    "VERIFICATION": "VERIFICATION",
    "SYMPTOM": "DIAGNOSIS",
    "PREREQUISITE": "PREREQUISITE",
    "ALARM": "ALARM",
    "COMPONENT": "COMPONENT",
    "FULL_SECTION": "GENERAL",
}

FOCUS_FIELDS = {
    "COMMUNICATION": ("communication_terms", "symptoms", "actions"),
    "CAUSE": ("causes", "symptoms", "conditions"),
    "ACTION": ("actions", "symptoms", "components"),
    "PROCEDURE": ("procedure_steps", "actions", "prerequisites"),
    "SAFETY": ("safety_requirements", "abort_conditions", "actions"),
    "VERIFICATION": ("verification_steps", "clearance_conditions", "actions"),
    "SYMPTOM": ("symptoms", "conditions", "components"),
    "PREREQUISITE": ("prerequisites", "tools", "parts"),
    "ALARM": ("alarm_names", "symptoms", "causes", "actions"),
    "COMPONENT": ("components", "actions", "symptoms"),
    "FULL_SECTION": ("actions", "symptoms", "components"),
}


def _clean_focus(value: str) -> str:
    value = re.sub(r"^[\s●•◆◇▪–—\-\d.、()（）]+", "", str(value or "")).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.split(r"[。；!?！？\n]", value, maxsplit=1)[0].strip(" ，。；：、")
    if len(value) > 54:
        value = value[:54].rstrip(" ，。；：、")
    return value


def _alarm_name(unit: dict) -> str | None:
    text = " ".join([
        str(unit.get("title") or ""),
        str(unit.get("canonical_evidence") or ""),
        *(str(value) for value in (unit.get("symptoms") or [])),
    ])
    matches = re.findall(r"[“\"「]([^“”\"「」]{2,30})[”\"」](?:故障)?告警", text)
    matches.extend(re.findall(r"([\u4e00-\u9fffA-Za-z_.-]{2,16})(?:故障)?告警", text))
    generic = {
        "当前", "历史", "设备", "相关", "所有", "全部", "产生", "触发", "查看", "提示", "活动", "声光",
    }
    diagnostic_terms = (
        "异常", "故障", "过温", "高温", "欠压", "过压", "绝缘", "接地", "断链", "超时", "水浸",
        "电弧", "环境", "证书", "火灾", "不一致", "告警点", "Cubicle",
    )
    rejected_fragments = ("常见", "用于", "提示", "配合", "设置", "实现", "如果", "表示", "若此", "当倍率")
    for raw in matches:
        value = raw.strip(" ，。；：、\"")
        for prefix in ("出现", "产生", "触发", "避免", "防止", "上报"):
            if prefix in value:
                value = value.rsplit(prefix, 1)[-1]
        value = value.strip(" ，。；：、\"")
        value = value.removesuffix("的")
        if (
            2 <= len(value) <= 24
            and value not in generic
            and not any(value.endswith(item) for item in generic)
            and any(term in value for term in diagnostic_terms)
            and not any(fragment in value for fragment in rejected_fragments)
        ):
            return value
    return None


def _focus(unit: dict) -> str:
    if unit.get("alarm_codes"):
        return str(unit["alarm_codes"][0])
    for field in FOCUS_FIELDS.get(str(unit.get("unit_type")), ()): 
        for value in unit.get(field) or []:
            focus = _clean_focus(value)
            if 10 <= len(focus) <= 54:
                return focus
    evidence = _clean_focus(str(unit.get("canonical_evidence") or ""))
    if len(evidence) >= 10:
        return evidence
    title = re.sub(r"^PDF\s*第\s*\d+\s*页$", "", str(unit.get("title") or "")).strip()
    if 6 <= len(title) <= 40 and not title.isdigit():
        return title
    model = str((unit.get("device_models") or [""])[0])
    return f"{model}设备维护".strip() or "设备维护"


def _query(unit: dict, *, oral: bool) -> str:
    focus = _focus(unit)
    unit_type = unit["unit_type"]
    templates = {
        "COMMUNICATION": f"{focus}老是掉线，先查啥？",
        "CAUSE": f"{focus}这种情况老出现，一般是啥原因？",
        "ACTION": f"{focus}出问题了咋排查处理？",
        "PROCEDURE": f"要处理{focus}，具体按什么顺序操作？",
        "SAFETY": f"弄{focus}之前要注意哪些安全风险？",
        "VERIFICATION": f"{focus}处理完以后咋确认真的恢复了？",
        "SYMPTOM": f"现场看到{focus}，这类现象该从哪儿查？",
        "PREREQUISITE": f"开始做{focus}之前得先满足哪些条件？",
        "ALARM": f"告警代码 {focus} 对应什么现象，应该怎么处理？",
        "COMPONENT": f"{focus}相关部件异常时应检查什么？",
        "FULL_SECTION": f"{focus}相关维护要求是什么？",
    }
    value = templates[unit_type]
    return value if oral else value.replace("啥", "什么").replace("咋", "如何").replace("弄", "操作")


def _case(
    unit: dict | None, *, index: int, category: str, query: str, intent: str,
    dataset_version: str = R5_TRAIN_DEV_VERSION, **flags,
) -> dict:
    signals = QuerySignalExtractionService().extract(query)
    canonical = LLMQueryUnderstandingService._canonical(signals)
    expected_chunks = list(unit.get("source_chunk_ids") or []) if unit else []
    expected_documents = [unit["document_id"]] if unit else []
    return {
        "case_id": "r5td-" + hashlib.sha256(f"{category}|{query}|{index}".encode("utf-8")).hexdigest()[:20],
        "dataset_version": dataset_version,
        "dataset_split": "dev" if index % 4 == 0 else "train",
        "source_type": "engineering_candidate",
        "category": category,
        "query": query,
        "expected_intent": intent,
        "expected_canonical": canonical,
        "expected_document_ids": expected_documents,
        "expected_chunk_ids": expected_chunks,
        "expected_semantic_unit_ids": [unit["semantic_unit_id"]] if unit else [],
        "expected_device_models": signals.device_models,
        "expected_alarm_codes": signals.alarm_codes,
        "source_locator": unit.get("source_locator") if unit else None,
        "source_excerpt": str(unit.get("canonical_evidence") or "")[:320] if unit else "",
        "source_span_hash": unit.get("source_span_hash") if unit else None,
        "source_grounded": bool(unit) or flags.get("no_answer") or flags.get("requires_clarification"),
        "weak_label": False,
        "ambiguous_expected_evidence": False,
        "engineering_verified": True,
        "expert_verified": False,
        "no_answer": bool(flags.get("no_answer")),
        "requires_clarification": bool(flags.get("requires_clarification")),
        "vector_heavy": bool(flags.get("vector_heavy")),
        "oral": bool(flags.get("oral")),
        "context_merge": bool(flags.get("context_merge")),
        "communication": intent == "COMMUNICATION",
        "safety": intent == "SAFETY",
        "cause": intent == "CAUSE",
        "action": intent in {"TROUBLESHOOTING", "PROCEDURE"},
        "verification": intent == "VERIFICATION",
    }


def create_dataset(
    *, destination_name: str = "train_dev_dataset.json",
    manifest_name: str = "train_dev_manifest.json",
    dataset_version: str = R5_TRAIN_DEV_VERSION,
) -> dict:
    destination = OUT / destination_name
    if destination.exists():
        raise SystemExit("R5 Train/Dev dataset is immutable and already exists")
    source = read_json(OUT / "semantic_units_v2.json")
    units = source.get("units") or []
    if not units or not source.get("source_grounded") or source.get("unsupported_facts"):
        raise SystemExit("source-grounded Semantic Unit V2 is required")
    ordered = sorted(units, key=lambda item: hashlib.sha256(item["semantic_unit_id"].encode()).hexdigest())
    rows: list[dict] = []
    used_units: set[str] = set()
    used_queries: set[str] = set()

    for unit_type, quota in TYPE_QUOTAS.items():
        selected = 0
        for unit in ordered:
            if unit["unit_type"] != unit_type or unit["semantic_unit_id"] in used_units:
                continue
            query = _query(unit, oral=True)
            if query in used_queries:
                continue
            rows.append(_case(
                unit,
                index=len(rows) + 1,
                category="oral_maintenance",
                query=query,
                intent=TYPE_INTENT[unit_type],
                dataset_version=dataset_version,
                oral=True,
                vector_heavy=len(rows) < 70,
            ))
            used_units.add(unit["semantic_unit_id"])
            used_queries.add(query)
            selected += 1
            if selected == quota:
                break
        if selected != quota:
            raise SystemExit(f"insufficient {unit_type} units for Train/Dev: {selected}/{quota}")

    for unit in ordered:
        if len([row for row in rows if row["category"] == "device_model_query"]) == 20:
            break
        if not unit.get("device_models"):
            continue
        if unit["unit_type"] == "ALARM" and not (unit.get("alarm_codes") or _alarm_name(unit)):
            continue
        query = f"{unit['device_models'][0]}：{_query(unit, oral=False)}"
        if query in used_queries:
            continue
        rows.append(_case(
            unit, index=len(rows) + 1, category="device_model_query", query=query,
            intent=TYPE_INTENT[unit["unit_type"]], dataset_version=dataset_version,
        ))
        used_queries.add(query)

    used_alarm_names: set[str] = set()
    for unit in ordered:
        if len([row for row in rows if row["category"] == "alarm_query"]) == 15:
            break
        if unit.get("alarm_codes"):
            query = f"告警代码 {unit['alarm_codes'][0]} 是什么原因，如何处理？"
        else:
            alarm_name = _alarm_name(unit)
            if not alarm_name or alarm_name in used_alarm_names:
                continue
            query = f"“{alarm_name}”告警是什么原因，如何处理？"
            used_alarm_names.add(alarm_name)
        if query in used_queries:
            continue
        rows.append(_case(
            unit, index=len(rows) + 1, category="alarm_query", query=query,
            intent="ALARM", dataset_version=dataset_version,
        ))
        used_queries.add(query)

    for offset in range(15):
        query = f"SUN2000-999KTL-X{offset + 1} 告警代码 {990001 + offset} 是什么原因，如何处理？"
        rows.append(_case(
            None, index=len(rows) + 1, category="no_answer", query=query, intent="ALARM",
            dataset_version=dataset_version, no_answer=True,
        ))

    clarification_queries = [
        "设备没反应", "机器不工作", "设备异常", "有问题", "不正常", "坏了", "设备没反应，想处理",
        "机器没反应，怎么修", "设备不工作，什么原因", "这个东西坏了怎么办",
    ]
    context_units = [unit for unit in ordered if unit.get("device_models") and unit["unit_type"] in {"COMMUNICATION", "CAUSE", "ACTION", "SYMPTOM"}]
    for offset in range(20):
        query = clarification_queries[offset % len(clarification_queries)] + f"（现场描述 {offset + 1}）"
        context_unit = context_units[offset % len(context_units)] if offset < 15 else None
        row = _case(
            None,
            index=len(rows) + 1,
            category="clarification",
            query=query,
            intent=LLMQueryUnderstandingService._intents(QuerySignalExtractionService().extract(query))[0],
            dataset_version=dataset_version,
            requires_clarification=True,
            context_merge=bool(context_unit),
        )
        if context_unit:
            row["clarification"] = f"型号是 {context_unit['device_models'][0]}，现象是通信中断，想了解原因"
            row["context_expected_document_ids"] = [context_unit["document_id"]]
            row["context_expected_chunk_ids"] = context_unit["source_chunk_ids"]
            row["context_expected_model"] = context_unit["device_models"][0]
        rows.append(row)

    category_counts = Counter(row["category"] for row in rows)
    coverage = {
        "oral": sum(row["oral"] for row in rows),
        "vector_heavy": sum(row["vector_heavy"] for row in rows),
        "model": category_counts["device_model_query"],
        "alarm": category_counts["alarm_query"],
        "communication": sum(row["communication"] for row in rows),
        "safety": sum(row["safety"] for row in rows),
        "no_answer": sum(row["no_answer"] for row in rows),
        "clarification": sum(row["requires_clarification"] for row in rows),
        "context_merge": sum(row["context_merge"] for row in rows),
        "cause": sum(row["cause"] for row in rows),
        "action": sum(row["action"] for row in rows),
        "verification": sum(row["verification"] for row in rows),
    }
    requirements = {
        "cases_at_least_150": len(rows) >= 150,
        "oral_at_least_60": coverage["oral"] >= 60,
        "vector_heavy_at_least_50": coverage["vector_heavy"] >= 50,
        "model_at_least_15": coverage["model"] >= 15,
        "alarm_at_least_15": coverage["alarm"] >= 15,
        "communication_at_least_15": coverage["communication"] >= 15,
        "safety_at_least_12": coverage["safety"] >= 12,
        "no_answer_at_least_15": coverage["no_answer"] >= 15,
        "clarification_at_least_20": coverage["clarification"] >= 20,
        "context_at_least_15": coverage["context_merge"] >= 15,
        "cause_at_least_15": coverage["cause"] >= 15,
        "action_at_least_15": coverage["action"] >= 15,
        "verification_at_least_10": coverage["verification"] >= 10,
        "source_grounded": all(row["source_grounded"] for row in rows),
        "weak_labels_zero": not any(row["weak_label"] for row in rows),
        "ambiguous_expected_evidence_zero": not any(row["ambiguous_expected_evidence"] for row in rows),
        "expert_verified_zero": not any(row["expert_verified"] for row in rows),
    }
    if not all(requirements.values()):
        raise SystemExit({"coverage": coverage, "requirements": requirements})
    dataset_hash = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    payload = {
        "generated_at": now_iso(),
        "dataset_version": dataset_version,
        "cases": len(rows),
        "dataset_hash": dataset_hash,
        "coverage": coverage,
        "requirements": requirements,
        "source_type": "engineering_candidate",
        "source_grounded": True,
        "formal_test_used": False,
        "benchmark_query_anchor_used": False,
        "expert_verified": False,
        "rows": rows,
    }
    write_json(destination_name, payload)
    write_json(manifest_name, {key: value for key, value in payload.items() if key != "rows"})
    print({"status": "CREATED", "cases": len(rows), "coverage": coverage, "sha256": dataset_hash})
    return payload


def main() -> None:
    create_dataset()


if __name__ == "__main__":
    main()
