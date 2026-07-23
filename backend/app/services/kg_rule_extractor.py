from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class KGExtractionSource:
    source_type: str
    source_id: UUID | None
    text: str
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    contribution_id: UUID | None = None
    diagnosis_trace_id: str | None = None
    task_id: UUID | None = None
    maintenance_record_id: UUID | None = None
    media_id: UUID | None = None


class KGRuleExtractor:
    """Deterministic, source-local graph extraction for PV inverter documents.

    A relation is emitted only when both sides occur in the same sentence or
    list/table row.  This avoids manufacturing a Cartesian product from a
    whole knowledge chunk while preserving a precise evidence excerpt.
    """

    extractor_name = "rule_based_v2_local_evidence"

    MANUFACTURERS = {
        "huawei": ["华为", "Huawei"],
        "sungrow": ["阳光电源", "Sungrow"],
    }
    SERIES = {
        "SUN2000": ["SUN2000"],
        "FusionSolar": ["FusionSolar"],
        "SG": ["SG系列", "SG series", "SG"],
    }
    FAULTS = {
        "low_insulation_resistance": ["绝缘阻抗低", "绝缘阻抗异常", "low insulation resistance", "insulation resistance"],
        "communication_interruption": ["通信中断", "通信异常", "communication abnormal", "communication interruption"],
        "over_temperature": ["过温", "温度过高", "over temperature", "high temperature"],
        "mppt_abnormal": ["MPPT异常", "MPPT 异常", "MPPT低发电", "mppt abnormal", "low generation"],
        "grid_connection_fault": ["电网异常", "并网故障", "grid abnormal", "grid fault"],
    }
    COMPONENTS = {
        "inverter": ["逆变器", "inverter"], "dc_side": ["直流侧", "DC侧", "DC side"],
        "ac_side": ["交流侧", "AC侧", "AC side"], "string": ["组串", "string"],
        "mppt": ["MPPT"], "fan": ["风扇", "fan"], "heat_sink": ["散热器", "heat sink"],
        "communication_module": ["通信模块", "communication module"],
        "grounding_wire": ["接地线", "grounding wire"], "insulation_module": ["绝缘模块", "insulation module"],
    }
    SYMPTOMS = {
        "alarm": ["告警", "alarm"], "trip": ["跳闸", "trip"], "offline": ["离线", "offline"],
        "low_generation": ["发电量低", "低发电", "low generation"],
        "high_temperature": ["温度高", "高温", "high temperature"],
        "insulation_abnormal": ["绝缘异常", "insulation abnormal"],
    }
    CAUSES = {
        "moisture": ["受潮", "潮湿", "moisture"], "grounding_abnormal": ["接地异常", "grounding abnormal"],
        "cable_damage": ["线缆破损", "电缆破损", "cable damage"],
        "fan_blocked": ["风扇堵转", "风扇停转", "fan block", "fan stopped"],
        "communication_loose": ["通信线松动", "通信接头松动", "communication loose"],
        "firmware_abnormal": ["固件异常", "firmware abnormal"], "string_shading": ["组串遮挡", "遮挡", "string shading"],
    }
    ACTIONS = {
        "check": ["检查", "check"], "tighten": ["紧固", "tighten"], "replace": ["更换", "replace"],
        "clean": ["清理", "清洁", "clean"], "reset": ["复位", "reset"], "upgrade": ["升级", "upgrade"],
        "measure": ["测量", "measure"], "power_off": ["断电", "power off"],
    }
    SAFETY_RISKS = {
        "high_voltage": ["高压", "high voltage"], "power_off": ["断电", "停电", "power off"],
        "voltage_test": ["验电", "voltage test"], "ppe": ["绝缘手套", "护目镜", "PPE"],
        "grounding": ["接地", "grounding"], "discharge_wait": ["放电等待", "discharge wait"],
    }
    TOOLS = {
        "multimeter": ["万用表", "multimeter"], "insulation_tester": ["绝缘电阻测试仪", "insulation resistance tester"],
        "thermal_imager": ["热成像仪", "thermal imager"], "torque_wrench": ["扭矩扳手", "torque wrench"],
    }

    def extract(self, sources: list[KGExtractionSource]) -> list[dict[str, Any]]:
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for source in sources:
            if not (source.text or "").strip():
                continue
            for candidate in self._extract_source(source):
                candidates.setdefault(self._candidate_key(candidate), candidate)
        return list(candidates.values())

    def _extract_source(self, source: KGExtractionSource) -> list[dict[str, Any]]:
        manufacturer = self._normalize_manufacturer(source.manufacturer) or self._infer_manufacturer(source.text)
        product_series = self._normalize_series(source.product_series) or self._infer_series(source.text)
        device_type = source.device_type or "pv_inverter"
        candidates: list[dict[str, Any]] = []
        for segment in self._segments(source.text):
            evidence_text = self._evidence_excerpt(segment)
            matched = {
                "manufacturer": self._matched_nodes(self.MANUFACTURERS, "manufacturer", segment, manufacturer, product_series, device_type, source, evidence_text),
                "product_series": self._matched_nodes(self.SERIES, "product_series", segment, manufacturer, product_series, device_type, source, evidence_text),
                "fault": self._matched_nodes(self.FAULTS, "fault", segment, manufacturer, product_series, device_type, source, evidence_text),
                "component": self._matched_nodes(self.COMPONENTS, "component", segment, manufacturer, product_series, device_type, source, evidence_text),
                "symptom": self._matched_nodes(self.SYMPTOMS, "symptom", segment, manufacturer, product_series, device_type, source, evidence_text),
                "cause": self._matched_nodes(self.CAUSES, "cause", segment, manufacturer, product_series, device_type, source, evidence_text),
                "action": self._matched_nodes(self.ACTIONS, "action", segment, manufacturer, product_series, device_type, source, evidence_text),
                "safety_risk": self._matched_nodes(self.SAFETY_RISKS, "safety_risk", segment, manufacturer, product_series, device_type, source, evidence_text),
                "tool": self._matched_nodes(self.TOOLS, "tool", segment, manufacturer, product_series, device_type, source, evidence_text),
            }
            matched["alarm"] = self._alarm_nodes(segment, manufacturer, product_series, device_type, source, evidence_text)
            for nodes in matched.values():
                candidates.extend({"candidate_type": "node", "payload": node, "confidence": 0.72, "evidence_text": evidence_text} for node in nodes)
            candidates.extend(self._relations_for_segment(matched, source, evidence_text))
        return candidates

    def _relations_for_segment(self, matched: dict[str, list[dict[str, Any]]], source: KGExtractionSource, evidence_text: str) -> list[dict[str, Any]]:
        relations: list[dict[str, Any]] = []
        def connect(left: str, right: str, relation: str, label: str, confidence: float) -> None:
            for source_node in matched[left]:
                for target_node in matched[right]:
                    relations.append(self._edge_candidate(source_node, target_node, relation, label, source, evidence_text, confidence))
        connect("product_series", "manufacturer", "BELONGS_TO", "属于", 0.82)
        for fault in matched["fault"]:
            for group, relation, label, confidence in (
                ("symptom", "HAS_SYMPTOM", "表现为", 0.74), ("cause", "CAUSED_BY", "可能原因", 0.72),
                ("component", "CHECK_BY", "排查部件", 0.70), ("action", "RESOLVED_BY", "处理措施", 0.70),
                ("safety_risk", "HAS_SAFETY_RISK", "安全风险", 0.76), ("tool", "USES_TOOL", "使用工具", 0.70),
                ("alarm", "HAS_ALARM", "关联告警", 0.78),
            ):
                for target in matched[group]:
                    relations.append(self._edge_candidate(fault, target, relation, label, source, evidence_text, confidence))
        return relations

    def _matched_nodes(self, mapping: dict[str, list[str]], node_type: str, text: str, manufacturer: str | None, product_series: str | None, device_type: str, source: KGExtractionSource, evidence_text: str) -> list[dict[str, Any]]:
        return [self._node_payload(node_type, canonical, aliases[0], manufacturer, product_series, device_type, source, evidence_text, aliases=aliases)
                for canonical, aliases in mapping.items() if self._contains_any(text, aliases)]

    def _alarm_nodes(self, text: str, manufacturer: str | None, product_series: str | None, device_type: str, source: KGExtractionSource, evidence_text: str) -> list[dict[str, Any]]:
        codes: set[str] = set()
        patterns = (
            r"(?:告警(?:码|代码)?|Alarm(?:\s*(?:ID|code))?|Fault\s*code|故障码)\s*(?:为|是|:|：|#|编号)?\s*((?:ALM-|A-)?\d{3,6})\b",
            r"\b((?:ALM-|A-)\d{3,6})\b",
            r"^\s*(\d{3,6})\s*(?:[|,，\t]|[-–])\s*.*(?:告警|Alarm|Fault)",
        )
        for pattern in patterns:
            codes.update(match.group(1).upper() for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE))
        return [self._node_payload("alarm", code, code, manufacturer, product_series, device_type, source, evidence_text, aliases=[code]) for code in sorted(codes)[:20]]

    def _node_payload(self, node_type: str, canonical_name: str, display_name: str, manufacturer: str | None, product_series: str | None, device_type: str, source: KGExtractionSource, evidence_text: str, *, aliases: list[str] | None = None) -> dict[str, Any]:
        return {"node_type": node_type, "canonical_name": canonical_name, "display_name": display_name, "manufacturer": manufacturer,
                "product_series": product_series, "device_type": device_type, "properties_json": {}, "source_type": source.source_type,
                "source_id": str(source.source_id) if source.source_id else None, "aliases": aliases or [display_name],
                "evidence": self._evidence_payload(source, evidence_text)}

    def _edge_candidate(self, source_node: dict[str, Any], target_node: dict[str, Any], relation_type: str, display_relation: str, source: KGExtractionSource, evidence_text: str, confidence: float) -> dict[str, Any]:
        return {"candidate_type": "edge", "payload": {"source_node": source_node, "target_node": target_node, "relation_type": relation_type,
                "display_relation": display_relation, "properties_json": {}, "source_type": source.source_type,
                "source_id": str(source.source_id) if source.source_id else None, "evidence": self._evidence_payload(source, evidence_text)},
                "confidence": confidence, "evidence_text": evidence_text}

    @staticmethod
    def _evidence_payload(source: KGExtractionSource, evidence_text: str) -> dict[str, Any]:
        return {"source_type": source.source_type, "source_id": str(source.source_id) if source.source_id else None,
                "document_id": str(source.document_id) if source.document_id else None, "chunk_id": str(source.chunk_id) if source.chunk_id else None,
                "contribution_id": str(source.contribution_id) if source.contribution_id else None,
                "diagnosis_trace_id": source.diagnosis_trace_id, "task_id": str(source.task_id) if source.task_id else None,
                "maintenance_record_id": str(source.maintenance_record_id) if source.maintenance_record_id else None,
                "media_id": str(source.media_id) if source.media_id else None, "evidence_text": evidence_text}

    @staticmethod
    def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str]:
        payload = candidate.get("payload") or {}
        evidence = (payload.get("evidence") or {}).get("evidence_text") or candidate.get("evidence_text") or ""
        evidence_key = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        if candidate.get("candidate_type") == "node":
            identity = "|".join(str(payload.get(key) or "") for key in ("node_type", "canonical_name", "manufacturer", "product_series", "device_type"))
        else:
            start, end = payload.get("source_node") or {}, payload.get("target_node") or {}
            identity = "|".join((str(start.get("node_type") or ""), str(start.get("canonical_name") or ""), str(payload.get("relation_type") or ""), str(end.get("node_type") or ""), str(end.get("canonical_name") or "")))
        return str(candidate.get("candidate_type") or "unknown"), f"{identity}|{evidence_key}"

    def _infer_manufacturer(self, text: str) -> str | None:
        return next((value for value, aliases in self.MANUFACTURERS.items() if self._contains_any(text, aliases)), None)

    def _infer_series(self, text: str) -> str | None:
        return next((value for value, aliases in self.SERIES.items() if self._contains_any(text, aliases)), None)

    @staticmethod
    def _normalize_manufacturer(value: str | None) -> str | None:
        return value.lower() if value and value.lower() in {"huawei", "sungrow"} else None

    @staticmethod
    def _normalize_series(value: str | None) -> str | None:
        return value if value in {"SUN2000", "FusionSolar", "SG"} else None

    @staticmethod
    def _contains_any(text: str, aliases: list[str]) -> bool:
        for alias in aliases:
            if alias == "SG":
                if re.search(r"(?<![A-Za-z0-9])SG(?=(?:[-\s]?(?:\d|系列|series))|$)", text, flags=re.IGNORECASE):
                    return True
            elif re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.IGNORECASE) if alias.isascii() else alias in text:
                return True
        return False

    @staticmethod
    def _segments(text: str) -> list[str]:
        parts = re.split(r"(?<=[。！？.!?；;])\s+|[\r\n]+", text)
        return [" ".join(part.split())[:500] for part in parts if len(" ".join(part.split())) >= 4]

    @staticmethod
    def _evidence_excerpt(text: str) -> str:
        return " ".join(text.split())[:500]
