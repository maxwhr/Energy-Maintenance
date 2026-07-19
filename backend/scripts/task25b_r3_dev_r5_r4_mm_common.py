from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r4_mm"
DATASET_VERSION = "task25b_r3_dev_r5_r4_mm_train_dev_v1"
FORMAL_VERSION = "task25b_r3_dev_r5_r4_mm_zh_v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def read_json(path_or_name: str | Path) -> dict[str, Any]:
    path = Path(path_or_name)
    if not path.is_absolute():
        path = OUT / path
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(name: str, payload: dict[str, Any]) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if path.exists():
        raise SystemExit(f"immutable task artifact already exists: {path}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3) if ordered else 0.0


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


DETERMINISTIC_CASES: list[dict[str, Any]] = [
    {"query": "为什么逆变器反复重启？", "intent": "CAUSE", "terms": ["重启", "查询可能原因"], "clarify": False},
    {"query": "通信老是掉线，啥原因？", "intent": "CAUSE", "terms": ["通信中断", "查询可能原因"], "clarify": False},
    {"query": "夜间无数据白天正常，怎么回事？", "intent": "CAUSE", "terms": ["夜间", "白天", "查询可能原因"], "clarify": False},
    {"query": "风扇异常可能是什么原因？", "intent": "CAUSE", "terms": ["风扇", "查询可能原因"], "clarify": False},
    {"query": "什么导致绝缘阻抗偏低？", "intent": "CAUSE", "terms": ["绝缘", "查询可能原因"], "clarify": False},
    {"query": "温度过高应该怎么处理？", "intent": "TROUBLESHOOTING", "terms": ["温度", "查询排查方法"], "clarify": False},
    {"query": "网线接好后仍然离线，如何排查？", "intent": "TROUBLESHOOTING", "terms": ["网线", "离线", "查询排查方法"], "clarify": False},
    {"query": "WLAN连不上怎么办？", "intent": "TROUBLESHOOTING", "terms": ["WLAN", "连接失败", "查询排查方法"], "clarify": False},
    {"query": "逆变器不出力怎么解决？", "intent": "TROUBLESHOOTING", "terms": ["无功率输出", "查询排查方法"], "clarify": False},
    {"query": "指示灯不亮怎么查？", "intent": "TROUBLESHOOTING", "terms": ["指示灯不亮", "查询排查方法"], "clarify": False},
    {"query": "如何更换通信模块？", "intent": "PROCEDURE", "terms": ["通信模块", "查询操作步骤"], "clarify": False},
    {"query": "怎么操作停机流程？", "intent": "PROCEDURE", "terms": ["停机", "查询操作步骤"], "clarify": False},
    {"query": "如何配置RS485地址？", "intent": "PROCEDURE", "terms": ["RS485", "查询操作步骤"], "clarify": False},
    {"query": "更换风扇的步骤是什么？", "intent": "PROCEDURE", "terms": ["风扇", "查询操作步骤"], "clarify": False},
    {"query": "Modbus连接的检查步骤是什么？", "intent": "PROCEDURE", "terms": ["Modbus", "查询操作步骤"], "clarify": False},
    {"query": "高压场景检查要注意什么？", "intent": "SAFETY", "terms": ["高压", "查询安全要求"], "clarify": False},
    {"query": "能否带电更换通信模块？", "intent": "SAFETY", "terms": ["带电", "通信模块", "查询安全要求"], "clarify": False},
    {"query": "现场检查有哪些触电风险？", "intent": "SAFETY", "terms": ["触电", "查询安全要求"], "clarify": False},
    {"query": "拆卸逆变器安全吗？", "intent": "SAFETY", "terms": ["拆卸", "查询安全要求"], "clarify": False},
    {"query": "操作直流开关要做什么防护？", "intent": "SAFETY", "terms": ["直流开关", "防护", "查询安全要求"], "clarify": False},
    {"query": "告警代码 2001 是什么意思？", "intent": "ALARM", "terms": ["2001", "查询告警含义"], "clarify": False},
    {"query": "故障码 2032 的含义是什么？", "intent": "ALARM", "terms": ["2032", "查询告警含义"], "clarify": False},
    {"query": "告警代码 3011 如何解释？", "intent": "ALARM", "terms": ["3011", "查询告警含义"], "clarify": False},
    {"query": "这个告警是什么意思？", "intent": "ALARM", "terms": ["告警", "查询告警含义"], "clarify": True},
    {"query": "这个告警该怎么处理？", "intent": "TROUBLESHOOTING", "terms": ["告警", "查询排查方法"], "clarify": True},
    {"query": "启动设备前需要准备什么？", "intent": "PREREQUISITE", "terms": ["启动", "查询操作前提"], "clarify": False},
    {"query": "操作前应满足哪些条件？", "intent": "PREREQUISITE", "terms": ["操作前", "查询操作前提"], "clarify": False},
    {"query": "开始更换风扇前先做什么？", "intent": "PREREQUISITE", "terms": ["风扇", "查询操作前提"], "clarify": False},
    {"query": "并网前需要准备哪些工具？", "intent": "PREREQUISITE", "terms": ["并网", "查询操作前提"], "clarify": False},
    {"query": "升级前的前提条件是什么？", "intent": "PREREQUISITE", "terms": ["升级", "查询操作前提"], "clarify": False},
    {"query": "处理后怎么确认通信恢复？", "intent": "VERIFICATION", "terms": ["通信", "查询恢复验证方法"], "clarify": False},
    {"query": "维护完成后如何验证设备正常？", "intent": "VERIFICATION", "terms": ["维护", "查询恢复验证方法"], "clarify": False},
    {"query": "告警消除后怎么确认恢复？", "intent": "VERIFICATION", "terms": ["告警", "查询恢复验证方法"], "clarify": True},
    {"query": "更换网线后是否正常怎么确认？", "intent": "VERIFICATION", "terms": ["网线", "查询恢复验证方法"], "clarify": False},
    {"query": "重启后如何验证并网恢复？", "intent": "VERIFICATION", "terms": ["重启", "并网", "查询恢复验证方法"], "clarify": False},
    {"query": "RS485通信中断", "intent": "COMMUNICATION", "terms": ["RS485", "通信"], "clarify": True},
    {"query": "WLAN通信异常", "intent": "COMMUNICATION", "terms": ["WLAN", "通信"], "clarify": True},
    {"query": "4G网络离线", "intent": "COMMUNICATION", "terms": ["4G", "离线"], "clarify": True},
    {"query": "监控平台没有数据", "intent": "COMMUNICATION", "terms": ["监控平台无数据"], "clarify": True},
    {"query": "以太网通信中断为什么？", "intent": "CAUSE", "terms": ["以太网", "查询可能原因"], "clarify": False},
    {"query": "设备没反应", "intent": "GENERAL", "terms": ["没反应"], "clarify": True},
    {"query": "机器不工作", "intent": "GENERAL", "terms": ["设备", "不工作"], "clarify": True},
    {"query": "设备异常", "intent": "GENERAL", "terms": ["设备异常"], "clarify": True},
    {"query": "这个东西坏了怎么办", "intent": "TROUBLESHOOTING", "terms": ["坏了", "查询排查方法"], "clarify": True},
    {"query": "设备有问题", "intent": "GENERAL", "terms": ["有问题"], "clarify": True},
    {"query": "SUN2000-50KTL 告警代码 2001 是什么意思？", "intent": "ALARM", "terms": ["SUN2000-50KTL", "2001"], "clarify": False},
    {"query": "SmartLogger3000 RS485掉线为什么？", "intent": "CAUSE", "terms": ["SmartLogger3000", "RS485", "通信中断"], "clarify": False},
    {"query": "SUN2000-100KTL 晚上平台没数据，怎么处理？", "intent": "TROUBLESHOOTING", "terms": ["SUN2000-100KTL", "夜间", "监控平台无数据"], "clarify": False},
    {"query": "LUNA2000 指示灯不亮怎么查？", "intent": "TROUBLESHOOTING", "terms": ["LUNA2000", "指示灯不亮"], "clarify": False},
    {"query": "SUN2000 告警代码 2032 重启后仍未消除，为什么？", "intent": "CAUSE", "terms": ["SUN2000", "2032", "未", "重启后"], "clarify": False},
    {"query": "设备夜间掉线白天恢复，怎么查？", "intent": "TROUBLESHOOTING", "terms": ["夜间", "通信中断", "白天恢复"], "clarify": False},
    {"query": "WiFi连接失败怎么解决？", "intent": "TROUBLESHOOTING", "terms": ["WiFi", "连接失败"], "clarify": False},
    {"query": "温度过高处理后如何验证恢复？", "intent": "VERIFICATION", "terms": ["温度", "查询恢复验证方法"], "clarify": False},
    {"query": "操作前需要确认设备是否下电？", "intent": "PREREQUISITE", "terms": ["操作前", "下电"], "clarify": False},
    {"query": "通信模块更换有哪些风险？", "intent": "SAFETY", "terms": ["通信模块", "风险"], "clarify": False},
]


AMBIGUITY_CASES: list[dict[str, str]] = [
    {"query": "设备没反应", "expected": "无法上电"},
    {"query": "机器没反应", "expected": "没有功率输出"},
    {"query": "现场设备没反应", "expected": "无法通信"},
    {"query": "逆变器没反应", "expected": "没有显示"},
    {"query": "设备突然没反应", "expected": "无法上电"},
    {"query": "机器偶尔没反应", "expected": "没有功率输出"},
    {"query": "这台设备没反应", "expected": "无法通信"},
    {"query": "现场机器没反应", "expected": "没有显示"},
    {"query": "设备不工作", "expected": "无法上电"},
    {"query": "机器不工作", "expected": "没有功率输出"},
    {"query": "设备异常", "expected": "无法通信"},
    {"query": "机器异常", "expected": "无法上电"},
    {"query": "设备不正常", "expected": "没有功率输出"},
    {"query": "机器不正常", "expected": "无法通信"},
    {"query": "设备有问题", "expected": "无法上电"},
    {"query": "机器有问题", "expected": "没有功率输出"},
    {"query": "这个设备坏了", "expected": "无法通信"},
    {"query": "机器坏了", "expected": "无法上电"},
    {"query": "SUN2000设备没反应", "expected": "没有功率输出"},
    {"query": "SmartLogger设备没反应", "expected": "无法通信"},
]
