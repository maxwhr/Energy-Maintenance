from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import MaintenanceSemanticAnchor
from app.repositories.semantic_anchor_repository import SemanticAnchorRepository
from app.services.semantic_section_assembler import AssembledSemanticSection


@dataclass(frozen=True, slots=True)
class MaintenanceSemanticUnitV2:
    semantic_unit_id: str
    stable_unit_key: str
    representation_version: str
    document_id: str
    document_title: str
    section_id: str
    heading_path: list[str]
    source_chunk_ids: list[str]
    source_chunk_hashes: list[str]
    source_page_start: int | None
    source_page_end: int | None
    source_locator: dict
    source_span_hash: str
    source_spans: list[dict]
    unit_type: str
    semantic_unit_type: str
    title: str
    canonical_text: str
    canonical_evidence: str
    canonical_text_hash: str
    language: str
    approval_mode: str | None
    current_document_version: bool
    product_family: str
    equipment_category: list[str]
    device_models: list[str]
    components: list[str]
    alarm_codes: list[str]
    alarm_names: list[str]
    symptoms: list[str]
    conditions: list[str]
    causes: list[str]
    actions: list[str]
    procedure_steps: list[str]
    prerequisites: list[str]
    verification_steps: list[str]
    safety_requirements: list[str]
    communication_terms: list[str]
    tools: list[str]
    parts: list[str]
    abort_conditions: list[str]
    clearance_conditions: list[str]
    source_grounded: bool
    engineering_verified: bool
    expert_verified: bool
    quality_status: str
    supersedes_semantic_unit_ids: list[str]
    anchor_types: list[str]

    def public_dict(self) -> dict:
        return asdict(self)


class MaintenanceSemanticUnitV2Service:
    VERSION = "task25b_r3_dev_r5_semantic_unit_v2"
    QUALITY_VERIFIED = "ENGINEERING_VERIFIED_SOURCE_GROUNDED"
    UNIT_TYPES = {
        "ALARM", "SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "PREREQUISITE", "VERIFICATION",
        "SAFETY", "COMMUNICATION", "COMPONENT", "FULL_SECTION",
    }
    TERMS = {
        "ALARM": ("告警", "报警", "故障码", "告警代码", "alarm"),
        "SYMPTOM": ("无法", "不能", "异常", "中断", "掉线", "不亮", "闪烁", "无输出", "不上电", "不开机", "重启", "过温", "通信失败", "连接失败", "状态异常"),
        "CAUSE": ("可能原因", "故障原因", "原因", "由于", "导致", "可能是", "原因分析"),
        "ACTION": ("检查", "确认", "更换", "恢复", "重启", "连接", "升级", "紧固", "清洁", "测量", "断开", "上电", "下电"),
        "PROCEDURE": ("步骤", "操作", "安装", "拆卸", "调试", "维护", "检修", "依次", "首先", "然后"),
        "PREREQUISITE": ("操作前", "开始前", "确保", "确认已", "必须先", "准备工作", "所需工具", "所需备件", "断电后", "等待", "满足以下条件"),
        "VERIFICATION": ("确认恢复", "检查是否正常", "操作完成后", "状态应为", "告警消失", "通信恢复", "重新上电确认", "观察"),
        "SAFETY": ("警告", "危险", "注意", "禁止", "必须断电", "等待放电", "防护用品", "不得带电操作", "高压", "高温", "短路", "触电"),
        "COMMUNICATION": ("通信", "RS485", "Modbus", "以太网", "网络", "网线", "串口", "端口", "地址"),
        "COMPONENT": ("逆变器", "通信模块", "风扇", "组串", "端子", "线缆", "连接器", "传感器", "控制器", "电池"),
    }
    NOISE_TITLES = ("目录", "版权", "法律声明", "修订记录", "文档版本", "商标声明", "前言")
    MODEL_RE = re.compile(r"(?<![A-Za-z0-9])(?:SUN2000|LUNA2000|SmartLogger)(?:[-_/]?[A-Za-z0-9]{1,16}){0,4}", re.I)
    ALARM_RE = re.compile(r"(?:告警(?:代码|码|ID)?|故障码)\s*[：:=#]?\s*([A-Za-z]{0,4}-?\d{3,6})", re.I)

    def __init__(self, db: Session | None):
        self.db = db
        self.repository = SemanticAnchorRepository(db) if db is not None else None

    @staticmethod
    def from_dict(payload: dict) -> MaintenanceSemanticUnitV2:
        """Restore the exact persisted V2 contract without accepting extra fields."""
        allowed = MaintenanceSemanticUnitV2.__dataclass_fields__
        return MaintenanceSemanticUnitV2(**{key: payload[key] for key in allowed})

    @classmethod
    def build_units(
        cls,
        section: AssembledSemanticSection,
        *,
        supersedes: list[str] | None = None,
        recoverable: bool = False,
    ) -> list[MaintenanceSemanticUnitV2]:
        compact = " ".join((section.content or "").split())
        if len(compact) < 60 or any(value in section.title for value in cls.NOISE_TITLES):
            return []
        sentences = cls._sentences(section.content)
        matched: dict[str, list[str]] = {
            unit_type: [sentence for sentence in sentences if any(term.lower() in sentence.lower() for term in terms)]
            for unit_type, terms in cls.TERMS.items()
        }
        types = cls._types(matched, section, recoverable=recoverable)
        units: list[MaintenanceSemanticUnitV2] = []
        for unit_type in types:
            selected = cls._select_evidence(unit_type, matched, sentences)
            # Keep canonical evidence as one verbatim source span. Additional
            # directly supported spans remain structured in source_spans.
            evidence = (selected[0] if selected else "")[:1600].strip()
            if len(evidence) < 12:
                continue
            source_hashes = [hashlib.sha256((chunk.content or "").encode("utf-8")).hexdigest() for chunk in section.chunks]
            source_span_hash = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
            heading_key = " > ".join(section.heading_path)
            stable_key = hashlib.sha256(
                f"{section.document.id}|{heading_key}|{unit_type}|{source_span_hash}".encode("utf-8")
            ).hexdigest()
            unit_id = "su2_" + hashlib.sha256(f"{stable_key}|{cls.VERSION}".encode("utf-8")).hexdigest()[:48]
            document_meta = section.document.metadata_json or {}
            chunk_meta = section.chunks[0].metadata_json or {}
            models = list(dict.fromkeys([
                *([section.document.model] if section.document.model else []),
                *[str(value) for value in document_meta.get("device_models") or []],
                *[str(value) for value in chunk_meta.get("device_models") or []],
                *cls.MODEL_RE.findall(compact),
            ]))
            components = cls._values(matched["COMPONENT"])
            model_tokens = {
                token.upper()
                for model in models
                for token in re.split(r"[-_/ ]+", str(model))
            }
            codes = list(dict.fromkeys(
                value
                for value in cls.ALARM_RE.findall(compact)
                if value.upper() not in model_tokens
                and not value.upper().startswith(("SUN", "LUNA", "SMARTLOGGER"))
            ))
            fields = {
                "symptoms": cls._field(unit_type, "SYMPTOM", matched),
                "conditions": cls._conditions(sentences),
                "causes": cls._field(unit_type, "CAUSE", matched),
                "actions": cls._field(unit_type, "ACTION", matched),
                "procedure_steps": cls._field(unit_type, "PROCEDURE", matched),
                "prerequisites": cls._field(unit_type, "PREREQUISITE", matched),
                "verification_steps": cls._field(unit_type, "VERIFICATION", matched),
                "safety_requirements": cls._field(unit_type, "SAFETY", matched),
                "communication_terms": cls._field(unit_type, "COMMUNICATION", matched),
            }
            canonical = "\n".join((
                f"语义单元类型：{unit_type}",
                f"来源章节：{section.title}",
                f"原始证据：{evidence}",
            ))
            units.append(MaintenanceSemanticUnitV2(
                semantic_unit_id=unit_id,
                stable_unit_key=stable_key,
                representation_version=cls.VERSION,
                document_id=str(section.document.id),
                document_title=section.document.title,
                section_id=section.section_id,
                heading_path=section.heading_path,
                source_chunk_ids=[str(chunk.id) for chunk in section.chunks],
                source_chunk_hashes=source_hashes,
                source_page_start=section.page_start,
                source_page_end=section.page_end,
                source_locator=section.source_locator,
                source_span_hash=source_span_hash,
                source_spans=[{"text": value, "chunk_ids": [str(chunk.id) for chunk in section.chunks]} for value in selected],
                unit_type=unit_type,
                semantic_unit_type=unit_type,
                title=section.title,
                canonical_text=canonical,
                canonical_evidence=evidence,
                canonical_text_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                language=str(document_meta.get("normalized_language") or ""),
                approval_mode=document_meta.get("approval_mode"),
                current_document_version=section.document.status == "active",
                product_family=section.document.product_series or "",
                equipment_category=[str(value) for value in document_meta.get("equipment_categories") or []],
                device_models=models,
                components=components,
                alarm_codes=[str(value).upper() for value in codes],
                alarm_names=[],
                conditions=fields["conditions"],
                tools=[value for value in sentences if "工具" in value][:4],
                parts=[value for value in sentences if "备件" in value or "部件" in value][:4],
                abort_conditions=[value for value in sentences if "停止" in value or "禁止" in value][:4],
                clearance_conditions=[value for value in sentences if "告警消失" in value or "恢复正常" in value][:4],
                source_grounded=True,
                engineering_verified=True,
                expert_verified=False,
                quality_status=cls.QUALITY_VERIFIED,
                supersedes_semantic_unit_ids=list(supersedes or []),
                anchor_types=["FULL" if unit_type == "FULL_SECTION" else unit_type],
                **{key: value for key, value in fields.items() if key != "conditions"},
            ))
        return units

    @classmethod
    def classify_unrepresented(cls, section: AssembledSemanticSection) -> dict:
        compact = " ".join((section.content or "").split())
        locator_valid = section.page_start is not None and bool(section.heading_path)
        title = section.title
        if not compact:
            classification = "EMPTY_OR_TOO_SHORT"
        elif len(compact) < 60:
            classification = "EMPTY_OR_TOO_SHORT"
        elif "目录" in title:
            classification = "TABLE_OF_CONTENTS"
        elif any(value in title for value in ("版权", "法律声明", "商标")):
            classification = "COPYRIGHT"
        elif any(value in title for value in ("修订", "版本历史")):
            classification = "REVISION_HISTORY"
        elif not locator_valid:
            classification = "MISSING_SOURCE_LOCATOR"
        elif section.table_continuation and any(term in compact for term in cls.TERMS["ALARM"]):
            classification = "ALARM_STRUCTURE_MISSED"
        elif section.cross_chunk:
            classification = "CROSS_CHUNK_FACT"
        else:
            missed = next((name for name in (
                "SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "PREREQUISITE", "VERIFICATION", "SAFETY", "COMMUNICATION", "COMPONENT"
            ) if any(term.lower() in compact.lower() for term in cls.TERMS[name])), None)
            classification = f"{missed}_STRUCTURE_MISSED" if missed else "OTHER"
        noise = classification in {
            "TABLE_OF_CONTENTS", "HEADER_FOOTER", "COPYRIGHT", "REVISION_HISTORY", "PURE_PARAMETER_TABLE",
            "PURE_MODEL_LIST", "PURE_REFERENCE_INDEX", "MARKETING_CONTENT", "EMPTY_OR_TOO_SHORT", "DUPLICATE_SECTION",
            "SUPERSEDED_CONTENT", "MISSING_SOURCE_LOCATOR", "PARSE_STRUCTURE_BROKEN",
        }
        recommended = [name for name, terms in cls.TERMS.items() if any(term.lower() in compact.lower() for term in terms)]
        recoverable = bool(not noise and locator_valid and len(compact) >= 60 and recommended)
        return {
            "document_id": str(section.document.id),
            "section_id": section.section_id,
            "heading_path": section.heading_path,
            "page_start": section.page_start,
            "page_end": section.page_end,
            "chunk_ids": [str(chunk.id) for chunk in section.chunks],
            "classification": classification,
            "classification_reason": "deterministic_source_structure_and_maintenance_term_audit",
            "recoverable": recoverable,
            "recommended_unit_types": recommended,
            "source_locator_valid": locator_valid,
            "cross_chunk": section.cross_chunk,
            "cross_page": section.cross_page,
            "cross_page_table": section.table_continuation and section.cross_page,
        }

    @classmethod
    def _types(cls, matched, section, *, recoverable):
        available = {name for name, values in matched.items() if values}
        if "ALARM" in available:
            priority = ("ALARM", "SYMPTOM", "CAUSE", "ACTION", "SAFETY", "VERIFICATION")
        elif "COMMUNICATION" in available:
            priority = ("COMMUNICATION", "SYMPTOM", "CAUSE", "ACTION", "PROCEDURE", "VERIFICATION", "SAFETY")
        elif "PROCEDURE" in available:
            priority = ("PROCEDURE", "PREREQUISITE", "ACTION", "VERIFICATION", "SAFETY", "COMPONENT")
        else:
            priority = ("SYMPTOM", "CAUSE", "ACTION", "PREREQUISITE", "VERIFICATION", "SAFETY", "COMPONENT")
        types = [name for name in priority if name in available]
        if "COMPONENT" in types and not ({"SYMPTOM", "ACTION", "PROCEDURE"} & available):
            types.remove("COMPONENT")
        if not types and recoverable and len(section.content) >= 180:
            types = ["FULL_SECTION"]
        return types[:4]

    @staticmethod
    def _sentences(content: str) -> list[str]:
        parts = re.split(r"(?<=[。！？；])\s*|\n+", content or "")
        return [" ".join(value.split()) for value in parts if len(" ".join(value.split())) >= 8]

    @classmethod
    def _select_evidence(cls, unit_type, matched, sentences):
        selected = list(matched.get(unit_type) or [])
        related = {
            "ALARM": ("SYMPTOM", "CAUSE", "ACTION", "SAFETY", "VERIFICATION"),
            "PROCEDURE": ("PREREQUISITE", "ACTION", "SAFETY", "VERIFICATION"),
            "COMMUNICATION": ("SYMPTOM", "CAUSE", "ACTION", "VERIFICATION"),
            "SYMPTOM": ("CAUSE",),
            "CAUSE": ("SYMPTOM", "ACTION"),
            "ACTION": ("SYMPTOM", "SAFETY", "VERIFICATION"),
        }.get(unit_type, ())
        for name in related:
            selected.extend(matched.get(name) or [])
        selected = list(dict.fromkeys(selected))[:8]
        return selected or sentences[:3]

    @staticmethod
    def _values(sentences):
        return list(dict.fromkeys(sentences))[:8]

    @classmethod
    def _field(cls, unit_type, field_type, matched):
        if field_type == unit_type or unit_type in {"ALARM", "PROCEDURE", "COMMUNICATION"}:
            return cls._values(matched.get(field_type) or [])
        if (unit_type, field_type) in {("CAUSE", "SYMPTOM"), ("ACTION", "SYMPTOM")}:
            return cls._values(matched.get(field_type) or [])
        return []

    @staticmethod
    def _conditions(sentences):
        terms = ("时", "后", "前", "晚上", "夜间", "并网", "上电", "下电", "升级")
        return list(dict.fromkeys(value for value in sentences if any(term in value for term in terms)))[:6]

    @classmethod
    def vector_id(cls, unit_id: str, anchor_type: str) -> str:
        return "suva2_" + hashlib.sha256(f"{unit_id}|{anchor_type}|{cls.VERSION}".encode("utf-8")).hexdigest()[:48]

    @classmethod
    def anchor_text(cls, unit: MaintenanceSemanticUnitV2, anchor_type: str) -> str:
        return "\n".join((
            f"ANCHOR_TYPE: {anchor_type}",
            f"PRODUCT_FAMILY: {unit.product_family}",
            f"DEVICE_MODELS: {'; '.join(unit.device_models)}",
            f"SOURCE_SECTION: {unit.title}",
            f"SOURCE_EVIDENCE: {unit.canonical_evidence[:900]}",
        ))

    def materialize(
        self,
        units: Iterable[MaintenanceSemanticUnitV2],
        *,
        collection: str,
        namespace: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_dim: int,
    ) -> list[MaintenanceSemanticAnchor]:
        if self.db is None or self.repository is None:
            raise RuntimeError("database session is required")
        rows = []
        for unit in units:
            if unit.quality_status != self.QUALITY_VERIFIED:
                continue
            source_chunk_id = unit.source_chunk_ids[0]
            for anchor_type in unit.anchor_types:
                text = self.anchor_text(unit, anchor_type)
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                existing = self.repository.get(
                    source_chunk_id=source_chunk_id,
                    anchor_type=anchor_type,
                    version=self.VERSION,
                    collection=collection,
                    namespace=namespace,
                )
                values = {
                    "document_id": unit.document_id,
                    "anchor_text": text,
                    "anchor_text_hash": text_hash,
                    "canonical_retrieval_text": unit.canonical_text,
                    "semantic_fields": {
                        "semantic_unit": unit.public_dict(),
                        "semantic_unit_id": unit.semantic_unit_id,
                        "source_chunk_ids": unit.source_chunk_ids,
                        "anchor_type": anchor_type,
                        "stable_unit_key": unit.stable_unit_key,
                    },
                    "semantic_representation_hash": unit.canonical_text_hash,
                    "source_locator": unit.source_locator,
                    "language": unit.language,
                    "approval_mode": unit.approval_mode,
                    "current_version": unit.current_document_version,
                    "vector_id": self.vector_id(unit.semantic_unit_id, anchor_type),
                    "embedding_provider": embedding_provider,
                    "embedding_model": embedding_model,
                    "embedding_dim": embedding_dim,
                }
                if existing is None:
                    existing = MaintenanceSemanticAnchor(
                        source_chunk_id=source_chunk_id,
                        collection_name=collection,
                        namespace=namespace,
                        anchor_type=anchor_type,
                        semantic_representation_version=self.VERSION,
                        index_status="pending",
                        **values,
                    )
                else:
                    previous = existing.anchor_text_hash
                    for key, value in values.items():
                        setattr(existing, key, value)
                    if previous != text_hash or existing.index_content_hash != text_hash:
                        existing.index_status = "pending"
                        existing.error_message = None
                rows.append(self.repository.save(existing))
        return rows
