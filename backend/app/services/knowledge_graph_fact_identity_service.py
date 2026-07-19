from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import KGEdge, KGNode


CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "huawei": ("华为", "Huawei"),
    "sungrow": ("阳光电源", "Sungrow"),
    "communication_interruption": ("通信中断", "通讯中断", "通信异常", "通信故障", "通信失败"),
    "low_insulation_resistance": ("绝缘阻抗低", "绝缘电阻低", "低绝缘阻抗", "绝缘阻抗异常"),
    "mppt_abnormal": ("MPPT异常", "MPPT 异常", "MPPT故障"),
    "over_temperature": ("过温", "温度过高", "过温故障"),
    "fan_blocked": ("风扇堵转", "风扇阻塞", "风扇卡住"),
    "grounding_abnormal": ("接地异常", "接地故障", "接地不良"),
    "moisture": ("受潮", "潮湿", "进水"),
    "ac_side": ("交流侧", "AC侧", "AC 侧"),
    "communication_module": ("通信模块", "通讯模块"),
    "dc_side": ("直流侧", "DC侧", "DC 侧"),
    "fan": ("风扇",),
    "clean": ("清理", "清洁", "除尘"),
    "measure": ("测量", "检测"),
    "power_off": ("断电", "下电", "切断电源", "关闭电源"),
    "high_voltage": ("高压风险", "高压", "高电压", "触电风险"),
    "ppe": ("个人防护", "个人防护用品", "防护用品", "绝缘手套", "PPE"),
    "alarm": ("告警", "报警"),
    "offline": ("离线", "掉线"),
    "insulation_tester": ("绝缘电阻测试仪", "绝缘电阻表", "绝缘测试仪", "兆欧表"),
    "multimeter": ("万用表",),
    "thermal_imager": ("热成像仪", "红外热像仪"),
}


class KnowledgeGraphFactIdentityService:
    """Builds stable, content-derived identities for active graph facts."""

    VERSION = "task25g_r2_graph_fact_identity_v1"

    @classmethod
    def normalize_key(cls, value: str | None) -> str:
        normalized = unicodedata.normalize("NFKC", value or "").strip().lower()
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", normalized)

    @classmethod
    def terms_for_node(cls, node: KGNode) -> list[str]:
        values = [node.canonical_name, node.display_name]
        values.extend(CONCEPT_ALIASES.get(cls.normalize_key(node.canonical_name), ()))
        values.extend(alias.alias for alias in getattr(node, "aliases", ()) or ())
        terms: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = " ".join(str(value or "").split()).strip()
            normalized = cls.normalize_key(cleaned)
            if not cleaned or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            terms.append(cleaned)
        return terms

    @classmethod
    def classify_node(cls, node: KGNode) -> str:
        if node.node_type in {"knowledge_chunk", "knowledge_document"}:
            return "HISTORICAL_ONLY_FACT"
        if node.node_type in {"manufacturer", "product_series", "device_model", "component", "alarm"}:
            return "IDENTITY_FACT"
        if node.node_type in {"fault", "symptom", "cause"}:
            return "DIAGNOSTIC_FACT"
        if node.node_type in {"action", "tool"}:
            return "ACTION_FACT"
        if node.node_type == "safety_risk":
            return "SAFETY_FACT"
        return "INVALID_OR_AMBIGUOUS_FACT"

    @classmethod
    def classify_edge(cls, edge: KGEdge) -> str:
        relation = edge.relation_type.upper()
        if relation == "DERIVED_FROM":
            return "HISTORICAL_ONLY_FACT"
        if relation == "BELONGS_TO":
            return "STRUCTURAL_FACT"
        if relation in {"HAS_FAULT", "HAS_ALARM", "HAS_SYMPTOM", "CAUSED_BY", "CHECK_BY"}:
            return "DIAGNOSTIC_FACT"
        if relation in {"RESOLVED_BY", "USES_TOOL"}:
            return "ACTION_FACT"
        if relation == "HAS_SAFETY_RISK":
            return "SAFETY_FACT"
        if relation in {"VERIFIED_BY", "CONFIRMED_BY", "RESTORED_BY"}:
            return "VERIFICATION_FACT"
        return "INVALID_OR_AMBIGUOUS_FACT"

    @classmethod
    def node_identity(cls, node: KGNode) -> dict[str, Any]:
        from app.services.task25g_r2_hashing import stable_hash

        properties = node.properties_json or {}
        identity = {
            "fact_id": f"node:{node.id}",
            "fact_kind": "NODE",
            "node_id": str(node.id),
            "node_type": node.node_type,
            "canonical_name": node.canonical_name,
            "display_name": node.display_name,
            "normalized_key": cls.normalize_key(node.canonical_name),
            "manufacturer": node.manufacturer,
            "product_family": node.product_series,
            "device_model": node.canonical_name if node.node_type == "device_model" else properties.get("device_model"),
            "alarm_code": node.canonical_name if node.node_type == "alarm" else properties.get("alarm_code"),
            "component": node.canonical_name if node.node_type == "component" else properties.get("component"),
            "status": node.status,
            "fact_category": cls.classify_node(node),
            "entity_terms": cls.terms_for_node(node),
            "identity_version": cls.VERSION,
        }
        stable_fields = {
            key: identity[key]
            for key in (
                "fact_kind",
                "node_type",
                "normalized_key",
                "manufacturer",
                "product_family",
                "device_model",
                "alarm_code",
                "component",
            )
        }
        identity["stable_fact_key"] = f"kg-node-{stable_hash(stable_fields)[:40]}"
        identity["identity_hash"] = stable_hash(identity)
        return identity

    @classmethod
    def edge_identity(cls, edge: KGEdge) -> dict[str, Any]:
        from app.services.task25g_r2_hashing import stable_hash

        source = edge.source_node
        target = edge.target_node
        source_identity = cls.node_identity(source)
        target_identity = cls.node_identity(target)
        properties = edge.properties_json or {}
        identity = {
            "fact_id": f"edge:{edge.id}",
            "fact_kind": "EDGE",
            "edge_id": str(edge.id),
            "source_node_id": str(edge.source_node_id),
            "source_node_type": source.node_type,
            "source_canonical_name": source.canonical_name,
            "source_display_name": source.display_name,
            "source_normalized_key": source_identity["normalized_key"],
            "source_terms": source_identity["entity_terms"],
            "relation_type": edge.relation_type,
            "target_node_id": str(edge.target_node_id),
            "target_node_type": target.node_type,
            "target_canonical_name": target.canonical_name,
            "target_display_name": target.display_name,
            "target_normalized_key": target_identity["normalized_key"],
            "target_terms": target_identity["entity_terms"],
            "manufacturer": source.manufacturer or target.manufacturer,
            "product_family": source.product_series or target.product_series,
            "device_model": properties.get("device_model"),
            "alarm_code": (
                source.canonical_name
                if source.node_type == "alarm"
                else target.canonical_name if target.node_type == "alarm" else properties.get("alarm_code")
            ),
            "component": (
                source.canonical_name
                if source.node_type == "component"
                else target.canonical_name if target.node_type == "component" else properties.get("component")
            ),
            "status": edge.status,
            "fact_category": cls.classify_edge(edge),
            "identity_version": cls.VERSION,
        }
        stable_fields = {
            "fact_kind": identity["fact_kind"],
            "source_stable_fact_key": source_identity["stable_fact_key"],
            "relation_type": identity["relation_type"],
            "target_stable_fact_key": target_identity["stable_fact_key"],
            "manufacturer": identity["manufacturer"],
            "product_family": identity["product_family"],
            "device_model": identity["device_model"],
            "alarm_code": identity["alarm_code"],
            "component": identity["component"],
        }
        identity["stable_fact_key"] = f"kg-edge-{stable_hash(stable_fields)[:40]}"
        identity["identity_hash"] = stable_hash(identity)
        return identity

    @classmethod
    def list_active_facts(cls, db: Session) -> list[dict[str, Any]]:
        nodes = list(
            db.scalars(
                select(KGNode)
                .options(selectinload(KGNode.aliases))
                .where(KGNode.status == "active")
                .order_by(KGNode.id)
            )
        )
        edges = list(
            db.scalars(
                select(KGEdge)
                .options(
                    selectinload(KGEdge.source_node).selectinload(KGNode.aliases),
                    selectinload(KGEdge.target_node).selectinload(KGNode.aliases),
                )
                .where(KGEdge.status == "active")
                .order_by(KGEdge.id)
            )
        )
        return [*(cls.node_identity(node) for node in nodes), *(cls.edge_identity(edge) for edge in edges)]
