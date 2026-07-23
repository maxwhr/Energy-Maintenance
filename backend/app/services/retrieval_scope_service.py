from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import KnowledgeDocument
from app.schemas.retrieval_scope import (
    CHINESE_ENGINEERING_PILOT_SCOPE_ID,
    HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
    SUNGROW_SG_FORMAL_SCOPE_ID,
    RetrievalScope,
)


class RetrievalScopeError(ValueError):
    pass


class RetrievalScopeService:
    HUAWEI_ALIASES = ("huawei", "华为")
    HUAWEI_PRODUCT_FAMILIES = ("SUN2000", "FusionSolar")
    OFFICIAL_SOURCE_TYPES = ("vendor_official", "vendor_official_html")
    REVIEWED_CONTRIBUTION_SOURCE_TYPES = ("knowledge_contribution", "user_upload")
    EXCLUDED_PRODUCT_MARKERS = ("luna2000", "smartlogger", "sungrow", "阳光电源")
    EXCLUDED_TITLE_MARKERS = (
        "task24", "task25", "fixture", "negative sample", "negative_sample", "demo-only", "demo only",
    )

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def resolve(self, scope_id: str | None, *, pilot_required: bool = False) -> RetrievalScope | None:
        if scope_id is None:
            if pilot_required:
                raise RetrievalScopeError("Pilot retrieval requires an explicit scope_id")
            return None
        if scope_id == HUAWEI_SUN2000_COMPETITION_SCOPE_ID:
            return self._resolve_huawei_sun2000_competition()
        if scope_id == SUNGROW_SG_FORMAL_SCOPE_ID:
            return self._resolve_sungrow_sg_formal()
        if scope_id != CHINESE_ENGINEERING_PILOT_SCOPE_ID:
            raise RetrievalScopeError(f"unsupported retrieval scope: {scope_id}")
        document_ids = tuple(self.db.scalars(select(KnowledgeDocument.id).where(
            KnowledgeDocument.status == "active", KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.review_status == "approved",
            KnowledgeDocument.metadata_json["normalized_language"].as_string() == "zh-CN",
            KnowledgeDocument.metadata_json["approved_for_pilot"].as_string() == "true",
            KnowledgeDocument.metadata_json["engineering_approved_for_pilot"].as_string() == "true",
            or_(KnowledgeDocument.metadata_json["marketing_only"].as_string().is_(None),
                KnowledgeDocument.metadata_json["marketing_only"].as_string() != "true"),
        ).order_by(KnowledgeDocument.id)))
        if not document_ids:
            raise RetrievalScopeError("Chinese engineering Pilot scope is empty")
        return RetrievalScope(
            scope_id=CHINESE_ENGINEERING_PILOT_SCOPE_ID,
            corpus_type="development_engineering_pilot", normalized_language="zh-CN",
            allowed_document_ids=document_ids, required_document_status="approved",
            required_chunk_status="active",
            required_approval_mode=("development_engineering_auto", "human_expert_approval"),
            approved_for_pilot=True, current_version_only=True,
            collection_name=self.settings.DASHVECTOR_PHYSICAL_COLLECTION, partition_name="pilot_r2",
        )

    def _resolve_huawei_sun2000_competition(self) -> RetrievalScope:
        document_ids = tuple(self.db.scalars(
            select(KnowledgeDocument.id)
            .where(*self._huawei_sun2000_sql_filters())
            .order_by(KnowledgeDocument.id)
        ))
        return RetrievalScope(
            scope_id=HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
            corpus_type="competition_delivery",
            normalized_language="zh-CN",
            allowed_document_ids=document_ids,
            required_document_status="approved",
            required_chunk_status="active",
            required_approval_mode=("approved", "human_expert_approval"),
            approved_for_pilot=False,
            current_version_only=True,
            collection_name=self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            partition_name="huawei_sun2000_competition_v1",
            manufacturer="huawei",
            product_families=self.HUAWEI_PRODUCT_FAMILIES,
            device_type="pv_inverter",
            allowed_source_types=(*self.OFFICIAL_SOURCE_TYPES, *self.REVIEWED_CONTRIBUTION_SOURCE_TYPES),
        )

    def _resolve_sungrow_sg_formal(self) -> RetrievalScope:
        document_ids = tuple(self.db.scalars(
            select(KnowledgeDocument.id)
            .where(
                func.lower(KnowledgeDocument.manufacturer) == "sungrow",
                KnowledgeDocument.product_series == "SG",
                KnowledgeDocument.device_type == "pv_inverter",
                KnowledgeDocument.status == "active",
                KnowledgeDocument.parse_status == "parsed",
                KnowledgeDocument.review_status == "approved",
            )
            .order_by(KnowledgeDocument.id)
        ))
        return RetrievalScope(
            scope_id=SUNGROW_SG_FORMAL_SCOPE_ID,
            corpus_type="formal_knowledge",
            normalized_language=None,
            allowed_document_ids=document_ids,
            required_document_status="approved",
            required_chunk_status="active",
            required_approval_mode=("approved", "human_expert_approval"),
            approved_for_pilot=False,
            current_version_only=True,
            collection_name=self.settings.DASHVECTOR_PHYSICAL_COLLECTION,
            partition_name="sungrow_sg_formal_v1",
            manufacturer="sungrow",
            product_families=("SG",),
            device_type="pv_inverter",
        )

    @classmethod
    def _huawei_sun2000_sql_filters(cls) -> list:
        metadata = KnowledgeDocument.metadata_json
        title_model = func.lower(func.concat(
            func.coalesce(KnowledgeDocument.title, ""), " ",
            func.coalesce(KnowledgeDocument.model, ""), " ",
            func.coalesce(metadata["product_family"].as_string(), ""), " ",
            func.coalesce(metadata["device_models"].as_string(), ""),
        ))
        official_source = KnowledgeDocument.source_type.in_(cls.OFFICIAL_SOURCE_TYPES)
        reviewed_contribution = and_(
            KnowledgeDocument.source_type.in_(cls.REVIEWED_CONTRIBUTION_SOURCE_TYPES),
            or_(
                metadata["competition_approved"].as_string() == "true",
                metadata["human_expert_approved"].as_string() == "true",
                metadata["approval_mode"].as_string() == "human_expert_approval",
            ),
        )
        return [
            func.lower(KnowledgeDocument.manufacturer).in_(cls.HUAWEI_ALIASES),
            KnowledgeDocument.product_series.in_(cls.HUAWEI_PRODUCT_FAMILIES),
            KnowledgeDocument.device_type == "pv_inverter",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.review_status == "approved",
            metadata["normalized_language"].as_string() == "zh-CN",
            or_(metadata["is_alternate_language"].as_string().is_(None),
                metadata["is_alternate_language"].as_string() != "true"),
            or_(metadata["is_test_fixture"].as_string().is_(None),
                metadata["is_test_fixture"].as_string() != "true"),
            or_(metadata["marketing_only"].as_string().is_(None),
                metadata["marketing_only"].as_string() != "true"),
            or_(metadata["quality_status"].as_string().is_(None),
                metadata["quality_status"].as_string() != "MARKETING_ONLY"),
            or_(metadata["is_current_version"].as_string().is_(None),
                metadata["is_current_version"].as_string() != "false"),
            or_(metadata["superseded_by_document_id"].as_string().is_(None),
                metadata["superseded_by_document_id"].as_string() == ""),
            or_(official_source, reviewed_contribution),
            *[not_(title_model.contains(marker)) for marker in cls.EXCLUDED_PRODUCT_MARKERS],
            *[not_(func.lower(KnowledgeDocument.title).contains(marker)) for marker in cls.EXCLUDED_TITLE_MARKERS],
        ]

    @classmethod
    def is_huawei_sun2000_document_eligible(cls, document: Any) -> bool:
        metadata = dict(getattr(document, "metadata_json", None) or {})
        manufacturer = str(getattr(document, "manufacturer", "") or "").strip().lower()
        product_series = str(getattr(document, "product_series", "") or "").strip()
        device_type = str(getattr(document, "device_type", "") or "").strip()
        source_type = str(getattr(document, "source_type", "") or "").strip()
        title = str(getattr(document, "title", "") or "")
        model = str(getattr(document, "model", "") or "")
        metadata_models = metadata.get("device_models") or []
        metadata_models_text = " ".join(str(item) for item in metadata_models) if isinstance(metadata_models, list) else str(metadata_models)
        product_text = " ".join((title, model, str(metadata.get("product_family") or ""), metadata_models_text)).lower()
        title_lower = title.lower()
        reviewed_contribution = source_type in cls.REVIEWED_CONTRIBUTION_SOURCE_TYPES and bool(
            metadata.get("competition_approved") is True
            or metadata.get("human_expert_approved") is True
            or metadata.get("approval_mode") == "human_expert_approval"
        )
        return bool(
            manufacturer in cls.HUAWEI_ALIASES
            and product_series in cls.HUAWEI_PRODUCT_FAMILIES
            and device_type == "pv_inverter"
            and getattr(document, "status", None) == "active"
            and getattr(document, "parse_status", None) == "parsed"
            and getattr(document, "review_status", None) == "approved"
            and metadata.get("normalized_language") == "zh-CN"
            and metadata.get("is_alternate_language") is not True
            and metadata.get("is_test_fixture") is not True
            and metadata.get("marketing_only") is not True
            and metadata.get("quality_status") != "MARKETING_ONLY"
            and metadata.get("is_current_version") is not False
            and not metadata.get("superseded_by_document_id")
            and (source_type in cls.OFFICIAL_SOURCE_TYPES or reviewed_contribution)
            and not any(marker in product_text for marker in cls.EXCLUDED_PRODUCT_MARKERS)
            and not any(marker in title_lower for marker in cls.EXCLUDED_TITLE_MARKERS)
        )
