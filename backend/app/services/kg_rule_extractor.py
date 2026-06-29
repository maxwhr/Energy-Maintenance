from __future__ import annotations

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
    extractor_name = "rule_based_v1"

    MANUFACTURERS = {
        "huawei": ["华为", "Huawei", "SUN2000", "FusionSolar"],
        "sungrow": ["阳光电源", "Sungrow", "SG"],
    }
    SERIES = {
        "SUN2000": ["SUN2000"],
        "FusionSolar": ["FusionSolar"],
        "SG": ["SG", "SG系列", "SG series"],
    }
    FAULTS = {
        "low_insulation_resistance": ["绝缘阻抗低", "绝缘阻抗异常", "low insulation resistance", "insulation resistance"],
        "communication_interruption": ["通信中断", "通信异常", "communication abnormal", "communication interruption"],
        "over_temperature": ["过温", "温度过高", "over temperature", "high temperature"],
        "mppt_abnormal": ["MPPT异常", "MPPT 异常", "MPPT低发电", "mppt abnormal", "low generation"],
        "grid_connection_fault": ["电网异常", "并网故障", "grid abnormal", "grid fault"],
    }
    COMPONENTS = {
        "inverter": ["逆变器", "inverter"],
        "dc_side": ["直流侧", "DC侧", "DC side"],
        "ac_side": ["交流侧", "AC侧", "AC side"],
        "string": ["组串", "string"],
        "mppt": ["MPPT"],
        "fan": ["风扇", "fan"],
        "heat_sink": ["散热器", "heat sink"],
        "communication_module": ["通信模块", "communication module"],
        "grounding_wire": ["接地线", "grounding wire"],
        "insulation_module": ["绝缘模块", "insulation module"],
    }
    SYMPTOMS = {
        "alarm": ["告警", "alarm"],
        "trip": ["跳闸", "trip"],
        "offline": ["离线", "offline"],
        "low_generation": ["发电量低", "低发电", "low generation"],
        "high_temperature": ["温度高", "高温", "high temperature"],
        "insulation_abnormal": ["绝缘异常", "insulation abnormal"],
    }
    CAUSES = {
        "moisture": ["受潮", "潮湿", "moisture"],
        "grounding_abnormal": ["接地异常", "grounding abnormal"],
        "cable_damage": ["线缆破损", "电缆破损", "cable damage"],
        "fan_blocked": ["风扇堵转", "风扇停转", "fan block", "fan stopped"],
        "communication_loose": ["通信线松动", "通信接头松动", "communication loose"],
        "firmware_abnormal": ["固件异常", "firmware abnormal"],
        "string_shading": ["组串遮挡", "遮挡", "string shading"],
    }
    ACTIONS = {
        "check": ["检查", "check"],
        "tighten": ["紧固", "tighten"],
        "replace": ["更换", "replace"],
        "clean": ["清理", "清洁", "clean"],
        "reset": ["复位", "reset"],
        "upgrade": ["升级", "upgrade"],
        "measure": ["测量", "measure"],
        "power_off": ["断电", "power off"],
    }
    SAFETY_RISKS = {
        "high_voltage": ["高压", "high voltage"],
        "power_off": ["断电", "停电", "power off"],
        "voltage_test": ["验电", "voltage test"],
        "ppe": ["绝缘手套", "护目镜", "PPE"],
        "grounding": ["接地", "grounding"],
        "discharge_wait": ["放电等待", "discharge wait"],
    }
    TOOLS = {
        "multimeter": ["万用表", "multimeter"],
        "insulation_tester": ["绝缘电阻测试仪", "insulation resistance tester"],
        "thermal_imager": ["热成像仪", "thermal imager"],
        "torque_wrench": ["扭矩扳手", "torque wrench"],
        "insulating_gloves": ["绝缘手套", "insulating gloves"],
    }

    def extract(self, sources: list[KGExtractionSource]) -> list[dict[str, Any]]:
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for source in sources:
            text = source.text or ""
            if not text.strip():
                continue
            source_candidates = self._extract_source(source, text)
            for candidate in source_candidates:
                key = self._candidate_key(candidate)
                if key in candidates:
                    existing = candidates[key]
                    existing["confidence"] = max(float(existing.get("confidence") or 0), float(candidate.get("confidence") or 0))
                    continue
                candidates[key] = candidate
        return list(candidates.values())

    def _extract_source(self, source: KGExtractionSource, text: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        evidence_text = self._evidence_excerpt(text)
        manufacturer = source.manufacturer or self._infer_manufacturer(text)
        product_series = source.product_series or self._infer_series(text)
        device_type = source.device_type or "pv_inverter"

        document_node = None
        chunk_node = None
        if source.document_id:
            document_node = self._node_payload(
                "knowledge_document",
                f"knowledge_document:{source.document_id}",
                "知识文档",
                manufacturer,
                product_series,
                device_type,
                source,
                evidence_text,
                properties={"document_id": str(source.document_id)},
            )
            candidates.append({"candidate_type": "node", "payload": document_node, "confidence": 0.75, "evidence_text": evidence_text})
        if source.chunk_id:
            chunk_node = self._node_payload(
                "knowledge_chunk",
                f"knowledge_chunk:{source.chunk_id}",
                "知识切片",
                manufacturer,
                product_series,
                device_type,
                source,
                evidence_text,
                properties={"chunk_id": str(source.chunk_id)},
            )
            candidates.append({"candidate_type": "node", "payload": chunk_node, "confidence": 0.75, "evidence_text": evidence_text})
            if document_node:
                candidates.append(self._edge_candidate(chunk_node, document_node, "DERIVED_FROM", "来源于", source, evidence_text, 0.75))

        manufacturer_nodes = self._matched_nodes(self.MANUFACTURERS, "manufacturer", text, manufacturer, product_series, device_type, source, evidence_text)
        series_nodes = self._matched_nodes(self.SERIES, "product_series", text, manufacturer, product_series, device_type, source, evidence_text)
        fault_nodes = self._matched_nodes(self.FAULTS, "fault", text, manufacturer, product_series, device_type, source, evidence_text)
        component_nodes = self._matched_nodes(self.COMPONENTS, "component", text, manufacturer, product_series, device_type, source, evidence_text)
        symptom_nodes = self._matched_nodes(self.SYMPTOMS, "symptom", text, manufacturer, product_series, device_type, source, evidence_text)
        cause_nodes = self._matched_nodes(self.CAUSES, "cause", text, manufacturer, product_series, device_type, source, evidence_text)
        action_nodes = self._matched_nodes(self.ACTIONS, "action", text, manufacturer, product_series, device_type, source, evidence_text)
        safety_nodes = self._matched_nodes(self.SAFETY_RISKS, "safety_risk", text, manufacturer, product_series, device_type, source, evidence_text)
        tool_nodes = self._matched_nodes(self.TOOLS, "tool", text, manufacturer, product_series, device_type, source, evidence_text)
        alarm_nodes = self._alarm_nodes(text, manufacturer, product_series, device_type, source, evidence_text)

        for node in [
            *manufacturer_nodes,
            *series_nodes,
            *fault_nodes,
            *component_nodes,
            *symptom_nodes,
            *cause_nodes,
            *action_nodes,
            *safety_nodes,
            *tool_nodes,
            *alarm_nodes,
        ]:
            candidates.append({"candidate_type": "node", "payload": node, "confidence": 0.68, "evidence_text": evidence_text})
            if chunk_node:
                candidates.append(self._edge_candidate(node, chunk_node, "MENTIONED_IN", "提及于", source, evidence_text, 0.62))

        for series_node in series_nodes:
            for manufacturer_node in manufacturer_nodes:
                candidates.append(self._edge_candidate(series_node, manufacturer_node, "BELONGS_TO", "属于", source, evidence_text, 0.8))
        for fault_node in fault_nodes:
            for symptom_node in symptom_nodes:
                candidates.append(self._edge_candidate(fault_node, symptom_node, "HAS_SYMPTOM", "表现为", source, evidence_text, 0.72))
            for cause_node in cause_nodes:
                candidates.append(self._edge_candidate(fault_node, cause_node, "CAUSED_BY", "可能原因", source, evidence_text, 0.68))
            for component_node in component_nodes:
                candidates.append(self._edge_candidate(fault_node, component_node, "CHECK_BY", "排查部件", source, evidence_text, 0.65))
            for action_node in action_nodes:
                candidates.append(self._edge_candidate(fault_node, action_node, "RESOLVED_BY", "处理措施", source, evidence_text, 0.65))
            for safety_node in safety_nodes:
                candidates.append(self._edge_candidate(fault_node, safety_node, "HAS_SAFETY_RISK", "安全风险", source, evidence_text, 0.75))
            for tool_node in tool_nodes:
                candidates.append(self._edge_candidate(fault_node, tool_node, "USES_TOOL", "使用工具", source, evidence_text, 0.64))
            for alarm_node in alarm_nodes:
                candidates.append(self._edge_candidate(fault_node, alarm_node, "HAS_ALARM", "关联告警", source, evidence_text, 0.7))

        return candidates

    def _matched_nodes(
        self,
        mapping: dict[str, list[str]],
        node_type: str,
        text: str,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        source: KGExtractionSource,
        evidence_text: str,
    ) -> list[dict[str, Any]]:
        nodes = []
        for canonical, aliases in mapping.items():
            if self._contains_any(text, aliases):
                nodes.append(
                    self._node_payload(
                        node_type,
                        canonical,
                        aliases[0],
                        manufacturer,
                        product_series,
                        device_type,
                        source,
                        evidence_text,
                        aliases=aliases,
                    )
                )
        return nodes

    def _alarm_nodes(
        self,
        text: str,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        source: KGExtractionSource,
        evidence_text: str,
    ) -> list[dict[str, Any]]:
        alarm_codes = set(re.findall(r"\b(?:ALM-|A-)?\d{3,6}\b", text, flags=re.IGNORECASE))
        return [
            self._node_payload(
                "alarm",
                code.upper(),
                code.upper(),
                manufacturer,
                product_series,
                device_type,
                source,
                evidence_text,
                aliases=[code],
            )
            for code in sorted(alarm_codes)
        ][:20]

    def _node_payload(
        self,
        node_type: str,
        canonical_name: str,
        display_name: str,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        source: KGExtractionSource,
        evidence_text: str,
        *,
        aliases: list[str] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "node_type": node_type,
            "canonical_name": canonical_name,
            "display_name": display_name,
            "manufacturer": manufacturer,
            "product_series": product_series,
            "device_type": device_type,
            "properties_json": properties or {},
            "source_type": source.source_type,
            "source_id": str(source.source_id) if source.source_id else None,
            "aliases": aliases or [display_name],
            "evidence": self._evidence_payload(source, evidence_text),
        }

    def _edge_candidate(
        self,
        source_node: dict[str, Any],
        target_node: dict[str, Any],
        relation_type: str,
        display_relation: str,
        source: KGExtractionSource,
        evidence_text: str,
        confidence: float,
    ) -> dict[str, Any]:
        return {
            "candidate_type": "edge",
            "payload": {
                "source_node": source_node,
                "target_node": target_node,
                "relation_type": relation_type,
                "display_relation": display_relation,
                "properties_json": {},
                "source_type": source.source_type,
                "source_id": str(source.source_id) if source.source_id else None,
                "evidence": self._evidence_payload(source, evidence_text),
            },
            "confidence": confidence,
            "evidence_text": evidence_text,
        }

    def _evidence_payload(self, source: KGExtractionSource, evidence_text: str) -> dict[str, Any]:
        return {
            "source_type": source.source_type,
            "source_id": str(source.source_id) if source.source_id else None,
            "document_id": str(source.document_id) if source.document_id else None,
            "chunk_id": str(source.chunk_id) if source.chunk_id else None,
            "contribution_id": str(source.contribution_id) if source.contribution_id else None,
            "diagnosis_trace_id": source.diagnosis_trace_id,
            "task_id": str(source.task_id) if source.task_id else None,
            "maintenance_record_id": str(source.maintenance_record_id) if source.maintenance_record_id else None,
            "media_id": str(source.media_id) if source.media_id else None,
            "evidence_text": evidence_text,
        }

    @staticmethod
    def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str]:
        payload = candidate.get("payload") or {}
        if candidate.get("candidate_type") == "node":
            return ("node", "|".join(str(payload.get(field) or "") for field in ("node_type", "canonical_name", "manufacturer", "product_series", "device_type")))
        if candidate.get("candidate_type") == "edge":
            source_node = payload.get("source_node") or {}
            target_node = payload.get("target_node") or {}
            return (
                "edge",
                "|".join(
                    [
                        str(source_node.get("node_type") or ""),
                        str(source_node.get("canonical_name") or ""),
                        str(payload.get("relation_type") or ""),
                        str(target_node.get("node_type") or ""),
                        str(target_node.get("canonical_name") or ""),
                    ]
                ),
            )
        return (str(candidate.get("candidate_type") or "unknown"), str(payload))

    def _infer_manufacturer(self, text: str) -> str | None:
        for value, aliases in self.MANUFACTURERS.items():
            if self._contains_any(text, aliases):
                return value
        return None

    def _infer_series(self, text: str) -> str | None:
        for value, aliases in self.SERIES.items():
            if self._contains_any(text, aliases):
                return value
        return None

    @staticmethod
    def _contains_any(text: str, aliases: list[str]) -> bool:
        text_lower = text.lower()
        return any(alias.lower() in text_lower for alias in aliases)

    @staticmethod
    def _evidence_excerpt(text: str) -> str:
        compact = " ".join(text.split())
        return compact[:500]
