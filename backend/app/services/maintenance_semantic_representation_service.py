from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.repositories.semantic_anchor_repository import SemanticAnchorRepository


@dataclass(frozen=True, slots=True)
class SemanticRepresentation:
    canonical_retrieval_text: str
    semantic_fields: dict
    representation_hash: str
    source_locator: dict


class MaintenanceSemanticRepresentationService:
    """Builds reproducible source-only maintenance semantics; no benchmark query or LLM is used."""

    VERSION = "task25b_r3_dev_r3_semantic_v1"
    COMPONENTS = {
        "通信": ("通信", "rs485", "modbus", "以太网", "网线", "网络", "地址"),
        "直流与组串": ("直流", "组串", "光伏", "mc4", "绝缘"),
        "交流与电网": ("交流", "电网", "并网", "电压", "频率"),
        "散热与风扇": ("风扇", "散热", "温度", "过温"),
        "储能连接": ("电池", "储能", "bat", "soc"),
        "接地与防护": ("接地", "防护", "触电", "危险", "警告", "安全"),
        "安装与接线": ("安装", "接线", "端子", "线缆", "连接器"),
    }
    ACTIONS = {
        "检查": ("检查", "核查", "确认"), "测量": ("测量", "检测", "测试"),
        "设置": ("设置", "配置", "参数"), "隔离": ("断开", "隔离", "关机", "禁止"),
        "更换或修复": ("更换", "紧固", "清洁", "修复"),
    }
    SAFETY = ("警告", "危险", "禁止", "防护", "接地", "触电", "断开")
    SYMPTOMS = ("告警", "故障", "异常", "中断", "失效", "过温")

    def __init__(self, db: Session):
        self.db = db
        self.repository = SemanticAnchorRepository(db)

    @staticmethod
    def _matches(content: str, rules: dict[str, tuple[str, ...]]) -> list[str]:
        lower = content.lower()
        return [name for name, needles in rules.items() if any(needle in lower for needle in needles)]

    @staticmethod
    def _first_terms(content: str, candidates: tuple[str, ...]) -> list[str]:
        lower = content.lower()
        return [term for term in candidates if term in lower]

    def build(self, chunk: KnowledgeChunk, document: KnowledgeDocument) -> SemanticRepresentation:
        content = " ".join((chunk.content or "").split())
        metadata = chunk.metadata_json or {}
        alarm = metadata.get("alarm_knowledge") or {}
        named_alarms = [str(item.get("alarm_name")) for item in (alarm.get("named_alarms") or []) if item.get("alarm_name")][:3]
        alarm_codes = [str(value) for value in ([*(metadata.get("fault_codes") or []), *(alarm.get("explicit_alarm_codes") or [])])][:5]
        semantic_fields = {
            "product_family": document.product_series or "",
            "equipment_category": list((document.metadata_json or {}).get("equipment_categories") or []),
            "device_model": document.model or "",
            "section": chunk.section_title or "",
            "components": self._matches(content, self.COMPONENTS),
            "alarm_names": named_alarms,
            "alarm_codes": alarm_codes,
            "fault_symptoms": self._first_terms(content, self.SYMPTOMS),
            "possible_causes": [],
            "actions": self._matches(content, self.ACTIONS),
            "safety_requirements": self._first_terms(content, self.SAFETY),
            "source_excerpt": content[:360],
        }
        lines = (
            ("产品族", semantic_fields["product_family"]), ("设备类别", "、".join(semantic_fields["equipment_category"])),
            ("设备型号", semantic_fields["device_model"]), ("章节", semantic_fields["section"]),
            ("部件", "、".join(semantic_fields["components"])), ("告警名称", "、".join(semantic_fields["alarm_names"])),
            ("告警代码", "、".join(semantic_fields["alarm_codes"])), ("故障现象", "、".join(semantic_fields["fault_symptoms"])),
            ("可能原因", ""), ("处理步骤", "、".join(semantic_fields["actions"])),
            ("安全要求", "、".join(semantic_fields["safety_requirements"])), ("原文摘要", semantic_fields["source_excerpt"]),
        )
        canonical = "\n".join(f"{key}：{value}" for key, value in lines)
        locator = {"page_number": chunk.page_number, "section_title": chunk.section_title,
                   "heading_path": metadata.get("heading_path") or metadata.get("section_path")}
        representation_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return SemanticRepresentation(canonical, semantic_fields, representation_hash, locator)

    @staticmethod
    def _anchor_text(anchor_type: str, representation: SemanticRepresentation) -> str:
        fields = representation.semantic_fields
        if anchor_type == "FULL_SEMANTIC":
            return representation.canonical_retrieval_text
        values = {
            "SYMPTOM": fields["fault_symptoms"], "CAUSE": fields["possible_causes"], "ACTION": fields["actions"],
            "SAFETY": fields["safety_requirements"], "ALARM": [*fields["alarm_names"], *fields["alarm_codes"]],
            "COMPONENT": fields["components"],
        }.get(anchor_type, [])
        return "\n".join((
            f"产品族：{fields['product_family']}", f"章节：{fields['section']}",
            f"{anchor_type}：{'、'.join(values)}", f"原文摘要：{fields['source_excerpt']}",
        ))

    @staticmethod
    def anchor_vector_id(source_chunk_id: object, anchor_type: str) -> str:
        return "sa_" + hashlib.sha256(f"{source_chunk_id}|{MaintenanceSemanticRepresentationService.VERSION}|{anchor_type}".encode("utf-8")).hexdigest()[:48]

    def materialize(
        self, *, chunks: list[tuple[KnowledgeChunk, KnowledgeDocument]], collection: str, namespace: str,
        embedding_provider: str, embedding_model: str, embedding_dim: int,
    ) -> list[MaintenanceSemanticAnchor]:
        anchors: list[MaintenanceSemanticAnchor] = []
        for chunk, document in chunks:
            representation = self.build(chunk, document)
            anchor_types = ["FULL_SEMANTIC"]
            fields = representation.semantic_fields
            if fields["fault_symptoms"]: anchor_types.append("SYMPTOM")
            if fields["possible_causes"]: anchor_types.append("CAUSE")
            if fields["actions"]: anchor_types.append("ACTION")
            if fields["safety_requirements"]: anchor_types.append("SAFETY")
            if fields["alarm_names"] or fields["alarm_codes"]: anchor_types.append("ALARM")
            if fields["components"]: anchor_types.append("COMPONENT")
            document_metadata = document.metadata_json or {}
            for anchor_type in anchor_types:
                text = self._anchor_text(anchor_type, representation)
                anchor_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                vector_id = self.anchor_vector_id(chunk.id, anchor_type)
                existing = self.repository.get(source_chunk_id=chunk.id, anchor_type=anchor_type, version=self.VERSION, collection=collection, namespace=namespace)
                values = {
                    "document_id": document.id, "anchor_text": text, "anchor_text_hash": anchor_hash,
                    "canonical_retrieval_text": representation.canonical_retrieval_text, "semantic_fields": representation.semantic_fields,
                    "semantic_representation_hash": representation.representation_hash, "source_locator": representation.source_locator,
                    "language": str(document_metadata.get("normalized_language") or ""),
                    "approval_mode": document_metadata.get("approval_mode"), "current_version": bool(metadata_value(document_metadata, "current_version", True)),
                    "vector_id": vector_id, "embedding_provider": embedding_provider, "embedding_model": embedding_model,
                    "embedding_dim": embedding_dim,
                }
                if existing is None:
                    existing = MaintenanceSemanticAnchor(source_chunk_id=chunk.id, collection_name=collection, namespace=namespace,
                                                         anchor_type=anchor_type, semantic_representation_version=self.VERSION,
                                                         index_status="pending", **values)
                else:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    if existing.index_content_hash != anchor_hash:
                        existing.index_status = "pending"; existing.error_message = None
                anchors.append(self.repository.save(existing))
        return anchors


def metadata_value(metadata: dict, key: str, default):
    value = metadata.get(key)
    return default if value is None else value
