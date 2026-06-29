from __future__ import annotations

from uuid import UUID

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Device,
    DiagnosisRecord,
    KnowledgeChunk,
    KnowledgeDocument,
    MaintenanceTask,
    SOPExecutionRecord,
    SOPTemplate,
)


class SOPRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_device(self, device_id: UUID) -> Device | None:
        return self.db.get(Device, device_id)

    def get_diagnosis_by_trace_id(self, trace_id: str) -> DiagnosisRecord | None:
        statement = select(DiagnosisRecord).where(DiagnosisRecord.trace_id == trace_id)
        return self.db.scalar(statement)

    def get_task(self, task_id: UUID) -> MaintenanceTask | None:
        return self.db.get(MaintenanceTask, task_id)

    def create_template(self, template: SOPTemplate) -> SOPTemplate:
        self.db.add(template)
        self.db.flush()
        self.db.refresh(template)
        return template

    def update_template(self, template: SOPTemplate) -> SOPTemplate:
        self.db.add(template)
        self.db.flush()
        self.db.refresh(template)
        return template

    def get_template(self, template_id: UUID, *, include_archived: bool = False) -> SOPTemplate | None:
        statement = select(SOPTemplate).where(SOPTemplate.id == template_id)
        if not include_archived:
            statement = statement.where(SOPTemplate.status != "archived")
        return self.db.scalar(statement)

    def list_templates(
        self,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = "pv_inverter",
        fault_type: str | None = None,
        maintenance_level: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SOPTemplate], int]:
        filters = []
        if manufacturer:
            filters.append(SOPTemplate.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(SOPTemplate.product_series == product_series)
        if device_type:
            filters.append(SOPTemplate.device_type == device_type)
        if fault_type:
            filters.append(SOPTemplate.fault_type == fault_type)
        if maintenance_level:
            filters.append(SOPTemplate.maintenance_level == maintenance_level)
        if status:
            filters.append(SOPTemplate.status == status)
        else:
            filters.append(SOPTemplate.status != "archived")
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    SOPTemplate.title.ilike(pattern),
                    SOPTemplate.compliance_notes.ilike(pattern),
                    cast(SOPTemplate.steps, Text).ilike(pattern),
                )
            )

        count_statement = select(func.count()).select_from(SOPTemplate)
        list_statement = select(SOPTemplate).order_by(SOPTemplate.updated_at.desc(), SOPTemplate.created_at.desc())
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        templates = list(
            self.db.scalars(
                list_statement.offset((page - 1) * page_size).limit(page_size)
            )
        )
        return templates, total

    def find_matching_template(
        self,
        *,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        fault_type: str | None,
        maintenance_level: str | None,
    ) -> SOPTemplate | None:
        if not fault_type:
            fault_type = "unknown"

        filters = [
            SOPTemplate.status == "active",
            SOPTemplate.device_type == device_type,
        ]
        if maintenance_level:
            filters.append(SOPTemplate.maintenance_level == maintenance_level)

        statement = (
            select(SOPTemplate)
            .where(*filters)
            .order_by(SOPTemplate.version.desc(), SOPTemplate.updated_at.desc(), SOPTemplate.created_at.desc())
        )
        candidates = list(self.db.scalars(statement))
        if not candidates:
            return None

        def priority(template: SOPTemplate) -> int:
            score = 0
            if template.fault_type == fault_type:
                score += 100
            elif template.fault_type == "unknown":
                score += 5
            else:
                return -1
            if manufacturer and template.manufacturer == manufacturer:
                score += 30
            elif template.manufacturer:
                score -= 10
            if product_series and product_series != "other" and template.product_series == product_series:
                score += 20
            elif template.product_series:
                score -= 5
            return score

        scored = [(priority(template), template) for template in candidates]
        scored = [item for item in scored if item[0] > 0]
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def search_reference_chunks(
        self,
        *,
        keywords: list[str],
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        fault_type: str | None,
        alarm_code: str | None,
        limit: int = 5,
    ) -> list[tuple[KnowledgeChunk, KnowledgeDocument]]:
        filters = [
            KnowledgeDocument.parse_status == "parsed",
            KnowledgeDocument.status == "active",
            KnowledgeDocument.review_status == "approved",
            KnowledgeChunk.status == "active",
            KnowledgeDocument.device_type == device_type,
            KnowledgeDocument.document_type.in_(["manual", "alarm_code", "sop", "fault_case", "inspection_standard"]),
        ]
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series and product_series != "other":
            filters.append(KnowledgeDocument.product_series == product_series)

        keyword_filters = []
        for keyword in keywords:
            if not keyword or len(keyword) < 2:
                continue
            pattern = f"%{keyword}%"
            keyword_filters.extend(
                [
                    KnowledgeChunk.content.ilike(pattern),
                    KnowledgeChunk.section_title.ilike(pattern),
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.summary.ilike(pattern),
                    KnowledgeDocument.source.ilike(pattern),
                ]
            )
        if fault_type:
            keyword_filters.append(cast(KnowledgeDocument.metadata_json, Text).ilike(f"%{fault_type}%"))
        if alarm_code:
            keyword_filters.append(KnowledgeChunk.content.ilike(f"%{alarm_code}%"))
        if keyword_filters:
            filters.append(or_(*keyword_filters))
        else:
            return []

        statement = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(*filters)
            .order_by(KnowledgeDocument.created_at.desc(), KnowledgeChunk.chunk_index.asc())
            .limit(limit * 8)
        )
        return [(row[0], row[1]) for row in self.db.execute(statement).all()]

    def create_execution(self, record: SOPExecutionRecord) -> SOPExecutionRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def update_execution(self, record: SOPExecutionRecord) -> SOPExecutionRecord:
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_execution(self, execution_id: UUID) -> SOPExecutionRecord | None:
        statement = (
            select(SOPExecutionRecord)
            .where(SOPExecutionRecord.id == execution_id)
            .options(selectinload(SOPExecutionRecord.template))
        )
        return self.db.scalar(statement)

    def list_executions(
        self,
        *,
        template_id: UUID | None = None,
        task_id: UUID | None = None,
        executor_id: UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SOPExecutionRecord], int]:
        filters = []
        if template_id:
            filters.append(SOPExecutionRecord.template_id == template_id)
        if task_id:
            filters.append(SOPExecutionRecord.task_id == task_id)
        if executor_id:
            filters.append(SOPExecutionRecord.executor_id == executor_id)
        if status:
            filters.append(SOPExecutionRecord.status == status)

        count_statement = select(func.count()).select_from(SOPExecutionRecord)
        list_statement = (
            select(SOPExecutionRecord)
            .options(selectinload(SOPExecutionRecord.template))
            .order_by(SOPExecutionRecord.updated_at.desc(), SOPExecutionRecord.created_at.desc())
        )
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)

        total = self.db.scalar(count_statement) or 0
        executions = list(
            self.db.scalars(
                list_statement.offset((page - 1) * page_size).limit(page_size)
            )
        )
        return executions, total
