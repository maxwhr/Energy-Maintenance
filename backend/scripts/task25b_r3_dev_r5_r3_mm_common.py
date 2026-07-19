from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r3_mm"
SOURCE_R5_R2 = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


MODEL_AB_CASES: list[dict[str, Any]] = [
    {"id": "ab01", "query": "通信老是掉线，啥原因？", "intent": "CAUSE", "terms": ["通信", "掉线"], "clarify": False},
    {"id": "ab02", "query": "设备夜间掉线，白天又好了，怎么排查？", "intent": "TROUBLESHOOTING", "terms": ["夜间", "掉线"], "clarify": False},
    {"id": "ab03", "query": "机器没反应", "intent": "GENERAL", "terms": ["响应"], "clarify": True},
    {"id": "ab04", "query": "逆变器为什么反复重启？", "intent": "CAUSE", "terms": ["重启"], "clarify": False},
    {"id": "ab05", "query": "现场状态不对，先查什么？", "intent": "TROUBLESHOOTING", "terms": ["状态"], "clarify": True},
    {"id": "ab06", "query": "更换通信模块前注意哪些安全风险？", "intent": "SAFETY", "terms": ["通信模块", "安全"], "clarify": False},
    {"id": "ab07", "query": "启动设备前要满足哪些条件？", "intent": "PREREQUISITE", "terms": ["启动", "条件"], "clarify": False},
    {"id": "ab08", "query": "处理完以后怎么确认通信已经恢复？", "intent": "VERIFICATION", "terms": ["通信", "恢复"], "clarify": False},
    {"id": "ab09", "query": "通信状态不正常", "intent": "COMMUNICATION", "terms": ["通信", "异常"], "clarify": True},
    {"id": "ab10", "query": "这个告警是什么意思？", "intent": "ALARM", "terms": ["告警"], "clarify": True},
    {"id": "ab11", "query": "怎样按顺序完成停机操作？", "intent": "PROCEDURE", "terms": ["停机", "操作"], "clarify": False},
    {"id": "ab12", "query": "温度过高应该怎么处理？", "intent": "TROUBLESHOOTING", "terms": ["温度", "处理"], "clarify": False},
    {"id": "ab13", "query": "风扇异常可能是什么原因？", "intent": "CAUSE", "terms": ["风扇", "原因"], "clarify": False},
    {"id": "ab14", "query": "网线接好后设备仍然离线，怎么排查？", "intent": "TROUBLESHOOTING", "terms": ["网线", "离线"], "clarify": False},
    {"id": "ab15", "query": "现场检查需要哪些安全防护？", "intent": "SAFETY", "terms": ["安全", "防护"], "clarify": False},
    {"id": "ab16", "query": "这个告警该怎么处理？", "intent": "ALARM", "terms": ["告警", "处理"], "clarify": True},
    {"id": "ab17", "query": "开始操作前需要准备什么？", "intent": "PREREQUISITE", "terms": ["操作", "准备"], "clarify": False},
    {"id": "ab18", "query": "完成维护后如何验证设备恢复？", "intent": "VERIFICATION", "terms": ["维护", "验证"], "clarify": False},
    {"id": "ab19", "query": "RS485通信中断", "intent": "COMMUNICATION", "terms": ["RS485", "通信"], "clarify": False},
    {"id": "ab20", "query": "设备有时候不对劲", "intent": "GENERAL", "terms": ["设备"], "clarify": True},
    {"id": "ab21", "query": "设备掉线，补充说明：只在晚上发生，我想知道原因", "intent": "CAUSE", "terms": ["晚上", "掉线"], "clarify": False},
    {"id": "ab22", "query": "机器没反应，补充说明：平台没有数据，应该怎么查", "intent": "TROUBLESHOOTING", "terms": ["平台", "数据"], "clarify": False},
    {"id": "ab23", "query": "夜间没有数据，白天正常，为什么？", "intent": "CAUSE", "terms": ["夜间", "白天"], "clarify": False},
    {"id": "ab24", "query": "Modbus连接失败的检查步骤是什么？", "intent": "PROCEDURE", "terms": ["Modbus", "步骤"], "clarify": False},
    {"id": "ab25", "query": "高压场景检查要注意什么？", "intent": "SAFETY", "terms": ["高压", "注意"], "clarify": False},
    {"id": "ab26", "query": "通信模块更换流程", "intent": "PROCEDURE", "terms": ["通信模块", "流程"], "clarify": False},
    {"id": "ab27", "query": "告警反复产生的原因是什么？", "intent": "CAUSE", "terms": ["告警", "原因"], "clarify": False},
    {"id": "ab28", "query": "处理后如何确认告警已经消除？", "intent": "VERIFICATION", "terms": ["告警", "确认"], "clarify": False},
    {"id": "ab29", "query": "WLAN无法连接应该怎么处理？", "intent": "TROUBLESHOOTING", "terms": ["WLAN", "连接"], "clarify": False},
    {"id": "ab30", "query": "设备异常", "intent": "GENERAL", "terms": ["设备", "异常"], "clarify": True},
]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(name: str, payload: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise SystemExit(f"immutable task artifact already exists: {name}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def safe_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    successful = [row for row in rows if row["structured_success"]]
    latencies = [float(row["latency_ms"]) for row in rows]
    true_positive = sum(row["predicted_clarification"] and row["expected_clarification"] for row in rows)
    false_positive = sum(row["predicted_clarification"] and not row["expected_clarification"] for row in rows)
    false_negative = sum(not row["predicted_clarification"] and row["expected_clarification"] for row in rows)
    metrics = {
        "cases": total,
        "structured_success": len(successful),
        "structured_success_ratio": ratio(len(successful), total),
        "tool_use_success_ratio": ratio(sum(row["tool_use_success"] for row in rows), total),
        "intent_accuracy": ratio(sum(row["intent_correct"] for row in rows), total),
        "canonicalization_accuracy": ratio(sum(row["canonicalization_correct"] for row in rows), total),
        "clarification_accuracy": ratio(sum(row["clarification_correct"] for row in rows), total),
        "clarification_precision": ratio(true_positive, true_positive + false_positive),
        "clarification_recall": ratio(true_positive, true_positive + false_negative),
        "hallucinated_models": sum(int(row["hallucinated_models"]) for row in rows),
        "hallucinated_alarms": sum(int(row["hallucinated_alarms"]) for row in rows),
        "provider_errors": sum(bool(row["provider_error_code"]) for row in rows),
        "timeouts": sum(row["provider_error_code"] == "TIMEOUT" for row in rows),
        "error_rate": ratio(sum(not row["structured_success"] for row in rows), total),
        "latency_ms": {
            "p50": round(percentile(latencies, 0.50) or 0.0, 3),
            "p95": round(percentile(latencies, 0.95) or 0.0, 3),
        },
        "token_usage": {
            "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
            "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
            "total_tokens": sum(int(row.get("total_tokens") or 0) for row in rows),
        },
    }
    gates = {
        "structured_success": metrics["structured_success_ratio"] >= 0.95,
        "intent_accuracy": metrics["intent_accuracy"] >= 0.95,
        "canonicalization": metrics["canonicalization_accuracy"] >= 0.90,
        "clarification_precision": metrics["clarification_precision"] >= 0.85,
        "clarification_recall": metrics["clarification_recall"] >= 0.85,
        "hallucinated_models": metrics["hallucinated_models"] == 0,
        "hallucinated_alarms": metrics["hallucinated_alarms"] == 0,
        "p95_ms": metrics["latency_ms"]["p95"] <= 4000.0,
        "error_rate": metrics["error_rate"] == 0.0,
    }
    metrics["gates"] = gates
    metrics["passed"] = all(gates.values())
    return metrics
