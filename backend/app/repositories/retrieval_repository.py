from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, DeviceMaintenanceRecord, KnowledgeChunk, KnowledgeDocument


class RetrievalRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def list_knowledge_candidates(
        self,
        *,
        keywords: list[str],
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = "pv_inverter",
        document_type: str | None = None,
        candidate_limit: int = 100,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        filters = [
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.status == "active",
        ]
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(KnowledgeDocument.product_series == product_series)
        if device_type:
            filters.append(KnowledgeDocument.device_type == device_type)
        if document_type:
            filters.append(KnowledgeDocument.document_type == document_type)

        keyword_filters = []
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

        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(*filters)
            .order_by(KnowledgeDocument.created_at.desc(), KnowledgeChunk.chunk_index.asc())
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
    ) -> int:
        filters = [
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.status == "active",
        ]
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
