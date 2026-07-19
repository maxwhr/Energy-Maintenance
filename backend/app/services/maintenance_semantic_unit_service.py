from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.repositories.semantic_anchor_repository import SemanticAnchorRepository
from app.services.maintenance_semantic_unit_v2_service import MaintenanceSemanticUnitV2Service


@dataclass(frozen=True, slots=True)
class MaintenanceSemanticUnit:
    semantic_unit_id: str
    document_id: str
    section_id: str
    source_chunk_ids: list[str]
    semantic_unit_type: str
    title: str
    canonical_text: str
    device_models: list[str]
    product_family: str
    equipment_category: list[str]
    alarm_codes: list[str]
    alarm_names: list[str]
    component_terms: list[str]
    symptom_terms: list[str]
    cause_terms: list[str]
    action_terms: list[str]
    safety_terms: list[str]
    prerequisite_terms: list[str]
    verification_terms: list[str]
    source_page_start: int | None
    source_page_end: int | None
    source_section: str
    source_locator: dict
    language: str
    approval_mode: str | None
    current_version: bool
    source_hash: str
    representation_version: str
    quality_status: str
    anchor_types: list[str]

    def public_dict(self) -> dict:
        return asdict(self)


class MaintenanceSemanticUnitService:
    """Build source-bounded maintenance units without benchmark queries or inferred facts."""

    VERSION = "task25b_r3_dev_r4_semantic_unit_v1"
    V2_VERSION = MaintenanceSemanticUnitV2Service.VERSION
    QUALITY_VERIFIED = "ENGINEERING_VERIFIED_SOURCE_GROUNDED"
    UNIT_TYPES = {
        "ALARM", "SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "SAFETY", "PREREQUISITE",
        "VERIFICATION", "COMPONENT", "COMMUNICATION", "FULL_SECTION",
    }
    TERMS = {
        "ALARM": ("告警", "故障码", "故障代码", "报警", "alarm"),
        "SYMPTOM": ("异常", "故障", "中断", "无法", "失败", "离线", "过温", "不工作", "无响应"),
        "CAUSE": ("原因", "导致", "由于", "可能是", "引起"),
        "ACTION": ("检查", "确认", "设置", "连接", "断开", "更换", "清洁", "紧固", "恢复", "重启", "关闭", "开启"),
        "PROCEDURE": ("步骤", "操作", "安装", "拆卸", "调试", "维护", "检修", "处理方法"),
        "SAFETY": ("警告", "危险", "安全", "触电", "断电", "接地", "防护", "禁止", "高压"),
        "PREREQUISITE": ("前提", "前置", "之前", "确保", "准备", "条件"),
        "VERIFICATION": ("验证", "确认完成", "检查结果", "恢复正常", "正常运行", "成功"),
        "COMPONENT": ("逆变器", "电池", "通信模块", "风扇", "组串", "端子", "线缆", "连接器", "传感器", "控制器"),
        "COMMUNICATION": ("通信", "rs485", "modbus", "以太网", "网络", "网线", "端口", "地址", "串口"),
    }
    NAVIGATION = ("目录", "修订记录", "版权所有", "法律声明", "商标声明", "前言", "文档版本")
    MARKETING = ("领先", "全场景", "全生命周期", "数字化", "高效智能", "宣传")
    ALARM_CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z]{1,4}-?\d{3,6}|\d{4,6})(?![A-Za-z0-9])")
    MODEL_RE = re.compile(r"\b(?:SUN2000|LUNA2000|SmartLogger)[A-Za-z0-9_./-]{2,}\b", re.IGNORECASE)

    def __init__(self, db: Session | None):
        self.db = db
        self.repository = SemanticAnchorRepository(db) if db is not None else None

    @staticmethod
    def _compact(value: str | None) -> str:
        return " ".join((value or "").split())

    @classmethod
    def _found_terms(cls, content: str, term_type: str) -> list[str]:
        lower = content.lower()
        return [term for term in cls.TERMS[term_type] if term.lower() in lower]

    @classmethod
    def _semantic_score(cls, content: str, section: str) -> int:
        joined = f"{section} {content}".lower()
        weights = {"ALARM": 3, "SYMPTOM": 2, "CAUSE": 2, "ACTION": 2, "PROCEDURE": 2,
                   "SAFETY": 2, "PREREQUISITE": 1, "VERIFICATION": 1, "COMPONENT": 1, "COMMUNICATION": 2}
        return sum(weights[key] for key, needles in cls.TERMS.items() if any(term.lower() in joined for term in needles))

    @classmethod
    def is_eligible(cls, chunks: list[KnowledgeChunk]) -> tuple[bool, str]:
        content = cls._compact(" ".join(chunk.content or "" for chunk in chunks))
        section = cls._compact(chunks[0].section_title if chunks else "")
        if not chunks or len(content) < 120:
            return False, "too_short"
        if any(noise in section for noise in cls.NAVIGATION) and cls._semantic_score(content, section) < 4:
            return False, "navigation_or_front_matter"
        if any(term in content[:240] for term in cls.MARKETING) and cls._semantic_score(content, section) < 4:
            return False, "marketing_without_maintenance_evidence"
        # A high-confidence unit needs several independent maintenance signals. This
        # deliberately leaves low-signal sections unrepresented instead of creating
        # anchors merely to reach a volume target.
        if cls._semantic_score(content, section) < 9:
            return False, "insufficient_maintenance_semantics"
        if not any(chunk.page_number is not None or chunk.section_title for chunk in chunks):
            return False, "missing_source_locator"
        return True, "eligible"

    @classmethod
    def _primary_type(cls, fields: dict[str, list[str]], section: str) -> str:
        if fields["alarm_codes"] or fields["alarm_names"] or (
            fields["ALARM"] and fields["SYMPTOM"] and fields["ACTION"] and ("告警" in section or "故障" in section)
        ):
            return "ALARM"
        if len(fields["COMMUNICATION"]) >= 1 and any(fields[key] for key in ("SYMPTOM", "ACTION")):
            return "COMMUNICATION"
        if len(fields["SAFETY"]) >= 2:
            return "SAFETY"
        if fields["PROCEDURE"] and fields["ACTION"]:
            return "PROCEDURE"
        if fields["CAUSE"] and fields["SYMPTOM"]:
            return "CAUSE"
        for candidate in ("SYMPTOM", "ACTION", "PREREQUISITE", "VERIFICATION", "COMPONENT"):
            if fields[candidate]:
                return candidate
        return "FULL_SECTION"

    @classmethod
    def build_unit(cls, chunks: list[KnowledgeChunk], document: KnowledgeDocument) -> MaintenanceSemanticUnit | None:
        eligible, _ = cls.is_eligible(chunks)
        if not eligible and str(document.document_type).upper() == "FAQ_TROUBLESHOOTING":
            faq_content = cls._compact(" ".join(chunk.content or "" for chunk in chunks))
            faq_section = cls._compact(chunks[0].section_title if chunks else "")
            eligible = len(faq_content) >= 100 and cls._semantic_score(faq_content, faq_section) >= 3
        if not eligible:
            return None
        content = cls._compact(" ".join(chunk.content or "" for chunk in chunks))
        section = cls._compact(chunks[0].section_title or "未命名来源章节")
        metadata = chunks[0].metadata_json or {}
        alarm_meta = metadata.get("alarm_knowledge") or {}
        fields: dict[str, list[str]] = {key: cls._found_terms(content, key) for key in cls.TERMS}
        extracted_codes = cls.ALARM_CODE_RE.findall(content)
        numeric_alarm_context = any(term in content.lower() for term in ("告警id", "告警码", "告警代码", "故障码", "alarm id"))
        extracted_codes = [value for value in extracted_codes if not value.isdigit() or numeric_alarm_context]
        fields["alarm_codes"] = list(dict.fromkeys([
            *[str(item) for item in (metadata.get("fault_codes") or [])],
            *[str(item) for item in (alarm_meta.get("explicit_alarm_codes") or [])],
            *extracted_codes,
        ]))[:8]
        fields["alarm_names"] = list(dict.fromkeys([
            str(item.get("alarm_name")) for item in (alarm_meta.get("named_alarms") or []) if item.get("alarm_name")
        ]))[:6]
        primary = cls._primary_type(fields, section)
        source_chunk_ids = [str(chunk.id) for chunk in chunks]
        source_hash = hashlib.sha256("|".join(
            hashlib.sha256((chunk.content or "").encode("utf-8")).hexdigest() for chunk in chunks
        ).encode("utf-8")).hexdigest()
        section_path = metadata.get("heading_path") or metadata.get("section_path") or [section]
        if not isinstance(section_path, list):
            section_path = [str(section_path)]
        section_key = " > ".join(str(value) for value in section_path if value) or section
        section_id = "sec_" + hashlib.sha256(f"{document.id}|{section_key}".encode("utf-8")).hexdigest()[:40]
        semantic_unit_id = "su_" + hashlib.sha256(
            f"{document.id}|{section_key}|{primary}|{source_hash}".encode("utf-8")
        ).hexdigest()[:48]
        document_meta = document.metadata_json or {}
        device_models = list(dict.fromkeys([
            *([document.model] if document.model else []), *[str(value) for value in (document_meta.get("device_models") or [])],
            *[str(value) for value in (metadata.get("device_models") or [])], *cls.MODEL_RE.findall(content),
        ]))
        equipment = [str(value) for value in (document_meta.get("equipment_categories") or metadata.get("equipment_categories") or [])]
        excerpt = content[:520]
        canonical_lines = [
            f"语义单元类型：{primary}", f"产品系列：{document.product_series or ''}",
            f"设备类别：{'、'.join(equipment)}", f"设备型号：{'、'.join(device_models)}",
            f"来源章节：{section}", f"部件：{'、'.join(fields['COMPONENT'])}",
            f"告警代码：{'、'.join(fields['alarm_codes'])}", f"告警名称：{'、'.join(fields['alarm_names'])}",
            f"故障现象：{'、'.join(fields['SYMPTOM'])}", f"可能原因：{'、'.join(fields['CAUSE'])}",
            f"处理动作：{'、'.join(fields['ACTION'])}", f"安全要求：{'、'.join(fields['SAFETY'])}",
            f"前置条件：{'、'.join(fields['PREREQUISITE'])}", f"完成验证：{'、'.join(fields['VERIFICATION'])}",
            f"原文证据：{excerpt}",
        ]
        canonical = "\n".join(canonical_lines)
        anchor_types = cls._anchor_types(primary, fields)
        pages = [chunk.page_number for chunk in chunks if chunk.page_number is not None]
        locator = {
            "page_start": min(pages) if pages else None, "page_end": max(pages) if pages else None,
            "section": section, "section_path": section_path, "source_chunk_ids": source_chunk_ids,
        }
        current = all(bool((chunk.metadata_json or {}).get("current_chunk_version", True)) for chunk in chunks)
        language = str(document_meta.get("normalized_language") or "")
        approved = bool(document_meta.get("approved_for_pilot")) and document.review_status == "approved" and document.status == "active"
        quality = cls.QUALITY_VERIFIED if language == "zh-CN" and current and approved and excerpt and locator["section"] else "NEEDS_SOURCE_REVIEW"
        return MaintenanceSemanticUnit(
            semantic_unit_id=semantic_unit_id, document_id=str(document.id), section_id=section_id,
            source_chunk_ids=source_chunk_ids, semantic_unit_type=primary, title=section, canonical_text=canonical,
            device_models=device_models, product_family=document.product_series or "", equipment_category=equipment,
            alarm_codes=fields["alarm_codes"], alarm_names=fields["alarm_names"], component_terms=fields["COMPONENT"],
            symptom_terms=fields["SYMPTOM"], cause_terms=fields["CAUSE"], action_terms=fields["ACTION"],
            safety_terms=fields["SAFETY"], prerequisite_terms=fields["PREREQUISITE"], verification_terms=fields["VERIFICATION"],
            source_page_start=locator["page_start"], source_page_end=locator["page_end"], source_section=section,
            source_locator=locator, language=language, approval_mode=document_meta.get("approval_mode"), current_version=current,
            source_hash=source_hash, representation_version=cls.VERSION, quality_status=quality, anchor_types=anchor_types,
        )

    @classmethod
    def _anchor_types(cls, primary: str, fields: dict[str, list[str]]) -> list[str]:
        if primary == "ALARM":
            candidates = ["ALARM", "SYMPTOM", "CAUSE", "ACTION", "SAFETY"]
        elif primary == "PROCEDURE":
            candidates = ["PROCEDURE", "PREREQUISITE", "ACTION", "VERIFICATION", "SAFETY", "COMPONENT"]
        elif primary == "COMMUNICATION":
            candidates = ["COMMUNICATION", "SYMPTOM", "ACTION"]
        elif primary == "SAFETY":
            candidates = ["SAFETY", "ACTION", "PROCEDURE"]
        elif primary == "CAUSE":
            candidates = ["CAUSE", "SYMPTOM", "ACTION"]
        elif primary == "SYMPTOM":
            candidates = ["SYMPTOM", "CAUSE", "ACTION"]
        elif primary == "ACTION":
            candidates = ["ACTION", "PROCEDURE", "SAFETY"]
        else:
            candidates = [primary]
        selected = []
        for anchor_type in candidates:
            if anchor_type in {primary, "FULL_SECTION", "ALARM", "PROCEDURE"} or fields.get(anchor_type):
                selected.append(anchor_type)
        return selected[:6]

    @classmethod
    def anchor_vector_id(cls, semantic_unit_id: str, anchor_type: str) -> str:
        return "suva_" + hashlib.sha256(f"{semantic_unit_id}|{anchor_type}|{cls.VERSION}".encode("utf-8")).hexdigest()[:48]

    @classmethod
    def anchor_text(cls, unit: MaintenanceSemanticUnit, anchor_type: str) -> str:
        # Typed anchors intentionally avoid copying the full canonical block.
        # Each representation keeps a short verbatim source-evidence tail and
        # only the source-derived fields relevant to that retrieval intent.
        evidence = unit.canonical_text.splitlines()[-1] if unit.canonical_text else ""
        common = [
            f"ANCHOR_TYPE: {anchor_type}",
            f"PRODUCT_FAMILY: {unit.product_family}",
            f"DEVICE_MODELS: {'; '.join(unit.device_models)}",
            f"SOURCE_SECTION: {unit.source_section}",
        ]
        typed_fields = {
            "ALARM": [unit.alarm_codes, unit.alarm_names, unit.symptom_terms, unit.cause_terms, unit.action_terms],
            "SYMPTOM": [unit.symptom_terms, unit.component_terms, unit.alarm_names],
            "CAUSE": [unit.cause_terms, unit.symptom_terms, unit.component_terms],
            "ACTION": [unit.action_terms, unit.symptom_terms, unit.safety_terms],
            "PROCEDURE": [unit.prerequisite_terms, unit.action_terms, unit.verification_terms, unit.safety_terms],
            "SAFETY": [unit.safety_terms, unit.action_terms, unit.prerequisite_terms],
            "PREREQUISITE": [unit.prerequisite_terms, unit.safety_terms, unit.action_terms],
            "VERIFICATION": [unit.verification_terms, unit.action_terms],
            "COMPONENT": [unit.component_terms, unit.symptom_terms, unit.action_terms],
            "COMMUNICATION": [unit.component_terms, unit.symptom_terms, unit.action_terms, unit.cause_terms],
            "FULL_SECTION": [[unit.title]],
        }.get(anchor_type, [[unit.title]])
        focused = ["; ".join(values) for values in typed_fields if values]
        return "\n".join([*common, f"INTENT_FIELDS: {' | '.join(focused)}", f"SOURCE_EVIDENCE: {evidence[:360]}"])

    def materialize(
        self, units: Iterable[MaintenanceSemanticUnit], *, collection: str, namespace: str,
        embedding_provider: str, embedding_model: str, embedding_dim: int,
    ) -> list[MaintenanceSemanticAnchor]:
        if self.db is None or self.repository is None:
            raise RuntimeError("database session is required to materialize semantic units")
        materialized: list[MaintenanceSemanticAnchor] = []
        for unit in units:
            if unit.quality_status != self.QUALITY_VERIFIED:
                continue
            source_chunk_id = unit.source_chunk_ids[0]
            for anchor_type in unit.anchor_types:
                text = self.anchor_text(unit, anchor_type)
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                vector_id = self.anchor_vector_id(unit.semantic_unit_id, anchor_type)
                existing = self.repository.get(
                    source_chunk_id=source_chunk_id, anchor_type=anchor_type, version=self.VERSION,
                    collection=collection, namespace=namespace,
                )
                values = {
                    "document_id": unit.document_id, "anchor_text": text, "anchor_text_hash": text_hash,
                    "canonical_retrieval_text": unit.canonical_text,
                    "semantic_fields": {"semantic_unit": unit.public_dict(), "semantic_unit_id": unit.semantic_unit_id,
                                        "source_chunk_ids": unit.source_chunk_ids, "anchor_type": anchor_type},
                    "semantic_representation_hash": hashlib.sha256(unit.canonical_text.encode("utf-8")).hexdigest(),
                    "source_locator": unit.source_locator, "language": unit.language, "approval_mode": unit.approval_mode,
                    "current_version": unit.current_version, "vector_id": vector_id,
                    "embedding_provider": embedding_provider, "embedding_model": embedding_model, "embedding_dim": embedding_dim,
                }
                if existing is None:
                    existing = MaintenanceSemanticAnchor(
                        source_chunk_id=source_chunk_id, collection_name=collection, namespace=namespace,
                        anchor_type=anchor_type, semantic_representation_version=self.VERSION,
                        index_status="pending", **values,
                    )
                else:
                    old_hash = existing.anchor_text_hash
                    for key, value in values.items():
                        setattr(existing, key, value)
                    if old_hash != text_hash or existing.index_content_hash != text_hash:
                        existing.index_status = "pending"
                        existing.error_message = None
                materialized.append(self.repository.save(existing))
        return materialized
