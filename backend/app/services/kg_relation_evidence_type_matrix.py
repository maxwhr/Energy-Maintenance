from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RelationEvidenceRule:
    relation_type: str
    semantic_unit_types: frozenset[str]
    relation_cues: tuple[str, ...]
    fact_category: str


class KGRelationEvidenceTypeMatrix:
    """Versioned generic relation-to-source contract without fact-specific branches."""

    VERSION = "task25g_r2_relation_evidence_matrix_v1"
    FULL_SECTION = "FULL_SECTION"

    NODE_UNIT_TYPES: dict[str, frozenset[str]] = {
        "manufacturer": frozenset({"COMPONENT", "ALARM", "PROCEDURE", "COMMUNICATION", "FULL_SECTION"}),
        "product_series": frozenset({"COMPONENT", "ALARM", "PROCEDURE", "COMMUNICATION", "FULL_SECTION"}),
        "device_model": frozenset({"COMPONENT", "ALARM", "PROCEDURE", "COMMUNICATION", "FULL_SECTION"}),
        "alarm": frozenset({"ALARM"}),
        "component": frozenset({"COMPONENT", "ACTION", "PROCEDURE", "ALARM", "COMMUNICATION"}),
        "fault": frozenset({"ALARM", "SYMPTOM", "CAUSE", "ACTION", "COMMUNICATION"}),
        "symptom": frozenset({"SYMPTOM", "ALARM", "COMMUNICATION"}),
        "cause": frozenset({"CAUSE", "ALARM", "COMMUNICATION"}),
        "action": frozenset({"ACTION", "PROCEDURE"}),
        "tool": frozenset({"ACTION", "PROCEDURE", "PREREQUISITE"}),
        "safety_risk": frozenset({"SAFETY", "PREREQUISITE", "PROCEDURE"}),
        "knowledge_chunk": frozenset({"FULL_SECTION"}),
        "knowledge_document": frozenset({"FULL_SECTION"}),
    }

    RULES: dict[str, RelationEvidenceRule] = {
        "BELONGS_TO": RelationEvidenceRule(
            "BELONGS_TO",
            frozenset({"COMPONENT", "ALARM", "PROCEDURE", "COMMUNICATION", "FULL_SECTION"}),
            ("属于", "隶属", "系列", "型号", "适用于", "由"),
            "STRUCTURAL_FACT",
        ),
        "HAS_FAULT": RelationEvidenceRule(
            "HAS_FAULT",
            frozenset({"ALARM", "SYMPTOM", "CAUSE", "ACTION", "COMMUNICATION"}),
            ("故障", "异常", "出现", "发生", "告警"),
            "DIAGNOSTIC_FACT",
        ),
        "HAS_ALARM": RelationEvidenceRule(
            "HAS_ALARM",
            frozenset({"ALARM"}),
            ("告警", "报警", "告警码", "告警代码", "故障码"),
            "DIAGNOSTIC_FACT",
        ),
        "HAS_SYMPTOM": RelationEvidenceRule(
            "HAS_SYMPTOM",
            frozenset({"SYMPTOM", "ALARM", "COMMUNICATION"}),
            ("现象", "表现", "出现", "无法", "异常", "离线", "告警"),
            "DIAGNOSTIC_FACT",
        ),
        "CAUSED_BY": RelationEvidenceRule(
            "CAUSED_BY",
            frozenset({"CAUSE", "ALARM", "COMMUNICATION"}),
            ("原因", "由于", "导致", "造成", "可能是", "引起"),
            "DIAGNOSTIC_FACT",
        ),
        "CHECK_BY": RelationEvidenceRule(
            "CHECK_BY",
            frozenset({"ACTION", "PROCEDURE", "COMMUNICATION", "ALARM"}),
            ("检查", "排查", "确认", "测量", "检测"),
            "DIAGNOSTIC_FACT",
        ),
        "RESOLVED_BY": RelationEvidenceRule(
            "RESOLVED_BY",
            frozenset({"ACTION", "PROCEDURE", "COMMUNICATION", "ALARM"}),
            ("处理", "解决", "清除", "恢复", "更换", "重启", "断电", "下电", "测量", "清洁", "清理"),
            "ACTION_FACT",
        ),
        "USES_TOOL": RelationEvidenceRule(
            "USES_TOOL",
            frozenset({"ACTION", "PROCEDURE", "PREREQUISITE"}),
            ("使用", "工具", "仪表", "万用表", "测试仪", "热像仪"),
            "ACTION_FACT",
        ),
        "HAS_SAFETY_RISK": RelationEvidenceRule(
            "HAS_SAFETY_RISK",
            frozenset({"SAFETY", "PREREQUISITE", "PROCEDURE"}),
            ("危险", "风险", "警告", "注意", "高压", "触电", "防护"),
            "SAFETY_FACT",
        ),
        "VERIFIED_BY": RelationEvidenceRule(
            "VERIFIED_BY",
            frozenset({"VERIFICATION", "PROCEDURE", "ACTION"}),
            ("确认", "验证", "复检", "恢复正常", "告警消失"),
            "VERIFICATION_FACT",
        ),
        "DERIVED_FROM": RelationEvidenceRule(
            "DERIVED_FROM",
            frozenset({"FULL_SECTION"}),
            ("来源", "摘自", "引用"),
            "HISTORICAL_ONLY_FACT",
        ),
    }

    @classmethod
    def node_type_compatible(cls, node_type: str, semantic_unit_type: str) -> bool:
        allowed = cls.NODE_UNIT_TYPES.get(node_type, frozenset())
        return semantic_unit_type in allowed and semantic_unit_type != cls.FULL_SECTION

    @classmethod
    def relation_rule(cls, relation_type: str) -> RelationEvidenceRule | None:
        return cls.RULES.get((relation_type or "").upper())

    @classmethod
    def relation_type_compatible(cls, relation_type: str, semantic_unit_type: str) -> bool:
        rule = cls.relation_rule(relation_type)
        return bool(rule and semantic_unit_type in rule.semantic_unit_types and semantic_unit_type != cls.FULL_SECTION)
