from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, and_, case, cast, desc, false, func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, DeviceMaintenanceRecord, KnowledgeChunk, KnowledgeDocument
from app.schemas.retrieval_scope import RetrievalScope


class RetrievalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    @staticmethod
    def _default_language_filter():
        language = KnowledgeDocument.metadata_json["normalized_language"].as_string()
        enabled = KnowledgeDocument.metadata_json["is_default_retrieval_language"].as_string()
        return and_(language == "zh-CN", enabled == "true")

    @staticmethod
    def _scope_filters(scope: RetrievalScope) -> list:
        if not scope.allowed_document_ids:
            return [false()]
        metadata = KnowledgeDocument.metadata_json
        filters = [
            KnowledgeDocument.id.in_(scope.allowed_document_ids),
            KnowledgeDocument.review_status == scope.required_document_status,
            KnowledgeChunk.status == scope.required_chunk_status,
        ]
        if scope.current_version_only:
            filters.extend([
                KnowledgeDocument.status == "active", KnowledgeDocument.parse_status == "parsed",
                or_(metadata["superseded_by_document_id"].as_string().is_(None),
                    metadata["superseded_by_document_id"].as_string() == ""),
            ])
        if scope.normalized_language and not scope.include_unknown_language:
            filters.append(metadata["normalized_language"].as_string() == scope.normalized_language)
        if scope.approved_for_pilot:
            filters.extend([
                metadata["approved_for_pilot"].as_string() == "true",
                metadata["engineering_approved_for_pilot"].as_string() == "true",
            ])
        if not scope.include_alternate_language:
            filters.append(or_(metadata["is_alternate_language"].as_string().is_(None),
                               metadata["is_alternate_language"].as_string() != "true"))
        if not scope.include_test_fixture:
            filters.append(or_(metadata["is_test_fixture"].as_string().is_(None),
                               metadata["is_test_fixture"].as_string() != "true"))
        if not scope.include_marketing:
            filters.extend([
                or_(metadata["marketing_only"].as_string().is_(None), metadata["marketing_only"].as_string() != "true"),
                or_(metadata["quality_status"].as_string().is_(None), metadata["quality_status"].as_string() != "MARKETING_ONLY"),
            ])
        if not scope.include_superseded:
            filters.append(KnowledgeDocument.status == "active")
        return filters

    def list_knowledge_candidates(
        self,
        *,
        keywords: list[str],
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = "pv_inverter",
        document_type: str | None = None,
        candidate_limit: int = 100,
        scope: RetrievalScope | None = None,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        filters = [
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.status == "active",
        ]
        filters.extend(self._scope_filters(scope) if scope else [self._default_language_filter()])
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(KnowledgeDocument.product_series == product_series)
        if device_type:
            filters.append(KnowledgeDocument.device_type == device_type)
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)

        keyword_filters = []
        ranking_terms = sorted((item for item in keywords if len(item) >= 3), key=len, reverse=True)[:8]
        for keyword in keywords:
            pattern = f"%{keyword}%"
            keyword_filters.extend(
                [
                    KnowledgeChunk.content.ilike(pattern),
                    KnowledgeChunk.section_title.ilike(pattern),
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.summary.ilike(pattern),
                    KnowledgeDocument.source.ilike(pattern),
                    cast(KnowledgeDocument.metadata_json, Text).ilike(pattern),
                ]
            )
        if keyword_filters:
            filters.append(or_(*keyword_filters))

        rank_expression = sum((
            case((KnowledgeChunk.section_title.ilike(f"%{term}%"), 10), else_=0)
            + case((KnowledgeDocument.title.ilike(f"%{term}%"), 8), else_=0)
            + case((KnowledgeChunk.content.ilike(f"%{term}%"), 5), else_=0)
            for term in ranking_terms
        ), 0)
        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(*filters)
            .order_by(desc(rank_expression), KnowledgeDocument.created_at.desc(), KnowledgeChunk.chunk_index.asc())
            .limit(candidate_limit)
        )
        return [(row[0], row[1]) for row in self.db.execute(statement).all()]

    def list_history_candidates(
        self,
        *,
        device_id: UUID,
        keywords: list[str],
        fault_type: str | None = None,
        alarm_code: str | None = None,
        candidate_limit: int = 20,
    ) -> list[DeviceMaintenanceRecord]:
        filters = [DeviceMaintenanceRecord.device_id == device_id]
        if fault_type:
            filters.append(
                or_(
                    DeviceMaintenanceRecord.fault_type == fault_type,
                    DeviceMaintenanceRecord.fault_type.ilike(f"%{fault_type}%"),
                )
            )
        if alarm_code:
            filters.append(DeviceMaintenanceRecord.alarm_code.ilike(f"%{alarm_code}%"))

        keyword_filters = []
        for keyword in keywords:
            pattern = f"%{keyword}%"
            keyword_filters.extend(
                [
                    DeviceMaintenanceRecord.fault_description.ilike(pattern),
                    DeviceMaintenanceRecord.root_cause.ilike(pattern),
                    DeviceMaintenanceRecord.repair_action.ilike(pattern),
                    DeviceMaintenanceRecord.verification_result.ilike(pattern),
                ]
            )
        if keyword_filters:
            filters.append(or_(*keyword_filters))

        statement = (
            select(DeviceMaintenanceRecord)
            .where(*filters)
            .order_by(desc(DeviceMaintenanceRecord.completed_at).nullslast(), DeviceMaintenanceRecord.created_at.desc())
            .limit(candidate_limit)
        )
        return list(self.db.scalars(statement))

    def list_recent_history_by_device(
        self,
        *,
        device_id: UUID,
        candidate_limit: int = 20,
    ) -> list[DeviceMaintenanceRecord]:
        statement = (
            select(DeviceMaintenanceRecord)
            .where(DeviceMaintenanceRecord.device_id == device_id)
            .order_by(desc(DeviceMaintenanceRecord.completed_at).nullslast(), DeviceMaintenanceRecord.created_at.desc())
            .limit(candidate_limit)
        )
        return list(self.db.scalars(statement))

    def count_chunks_for_filters(
        self,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = "pv_inverter",
        document_type: str | None = None,
        scope: RetrievalScope | None = None,
    ) -> int:
        filters = [
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.status == "active",
        ]
        filters.extend(self._scope_filters(scope) if scope else [self._default_language_filter()])
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(KnowledgeDocument.product_series == product_series)
        if device_type:
            filters.append(KnowledgeDocument.device_type == device_type)
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)
        statement = (
            select(func.count())
            .select_from(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(*filters)
        )
        return self.db.scalar(statement) or 0
