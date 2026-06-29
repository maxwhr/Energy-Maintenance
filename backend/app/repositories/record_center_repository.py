from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, inspect, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KGEdge,
    KGEvidenceLink,
    KGExtractionRun,
    KGNode,
    KnowledgeContribution,
    KnowledgeDocument,
    MaintenanceTask,
    QARecord,
    SOPExecutionRecord,
    SOPTemplate,
    UploadedMedia,
    User,
)


class RecordCenterRepository:
    def __init__(self, db: Session):
        self.db = db

    def overview(self) -> dict[str, Any]:
        recent_records = self._collect_items(record_type="all", page=1, page_size=8)["items"]
        return {
            "qa_records": self._count(QARecord),
            "diagnosis_records": self._count(DiagnosisRecord),
            "maintenance_tasks": self._count(MaintenanceTask),
            "maintenance_records": self._count(DeviceMaintenanceRecord),
            "sop_executions": self._count(SOPExecutionRecord),
            "knowledge_documents": self._count(KnowledgeDocument),
            "knowledge_contributions": self._count(KnowledgeContribution),
            "uploaded_media": self._count(UploadedMedia),
            "devices": self._count(Device),
            "knowledge_graph_nodes": self._count(KGNode),
            "knowledge_graph_edges": self._count(KGEdge),
            "knowledge_graph_extraction_runs": self._count(KGExtractionRun),
            "recent_records": recent_records,
        }

    def search(
        self,
        *,
        record_type: str = "all",
        device_id: UUID | None = None,
        keyword: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        return self._collect_items(
            record_type=record_type,
            device_id=device_id,
            keyword=keyword,
            trace_id=trace_id,
            status=status,
            fault_type=fault_type,
            alarm_code=alarm_code,
            manufacturer=manufacturer,
            product_series=product_series,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    def get_detail(self, *, record_type: str, record_id: UUID) -> dict[str, Any] | None:
        model = self._model_for_type(record_type)
        if not model:
            return None

        statement = select(model).where(model.id == record_id)
        if model is SOPExecutionRecord:
            statement = statement.options(selectinload(SOPExecutionRecord.template))
        if model is MaintenanceTask:
            statement = statement.options(selectinload(MaintenanceTask.device))
        record = self.db.scalar(statement)
        if not record:
            return None

        item = self._item_from_record(record_type, record)
        related = self._related_records(record_type=record_type, record=record)
        record_payload = self._record_dict(record)
        record_payload["media_items"] = [
            self._media_payload(media)
            for media in self._media_for_record(record_type=record_type, record=record)
        ]
        record_payload["knowledge_graph"] = self._kg_context_for_record(record_type=record_type, record=record)
        return {
            "record_type": record_type,
            "record_id": record_id,
            "record": record_payload,
            "related_records": related,
            "summary_item": item,
        }

    def device_timeline(
        self,
        *,
        device_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        record_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any] | None:
        device = self.db.get(Device, device_id)
        if not device:
            return None

        result = self.search(
            record_type=record_type or "all",
            device_id=device_id,
            date_from=date_from,
            date_to=date_to,
            page=1,
            page_size=max(1, min(limit, 200)),
        )
        timeline = [
            {
                "time": item["created_at"],
                "record_type": item["record_type"],
                "title": item["title"],
                "summary": item.get("summary"),
                "trace_id": item.get("trace_id"),
                "record_id": item["record_id"],
                "status": item.get("status"),
                "operator_name": item.get("created_by_name"),
            }
            for item in result["items"]
        ]
        return {
            "device": self._record_dict(device),
            "timeline": timeline,
        }

    def _collect_items(
        self,
        *,
        record_type: str,
        device_id: UUID | None = None,
        keyword: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        types = (
            [
                "qa",
                "diagnosis",
                "task",
                "maintenance_record",
                "sop_execution",
                "knowledge_document",
                "knowledge_contribution",
                "media",
                "knowledge_graph_node",
                "knowledge_graph_edge",
                "knowledge_graph_extraction_run",
            ]
            if record_type == "all"
            else [record_type]
        )
        items: list[dict[str, Any]] = []
        for current_type in types:
            items.extend(
                self._items_for_type(
                    current_type,
                    device_id=device_id,
                    keyword=keyword,
                    trace_id=trace_id,
                    status=status,
                    fault_type=fault_type,
                    alarm_code=alarm_code,
                    manufacturer=manufacturer,
                    product_series=product_series,
                    date_from=date_from,
                    date_to=date_to,
                )
            )

        fallback_time = datetime.min.replace(tzinfo=timezone.utc)
        items.sort(key=lambda item: item.get("created_at") or fallback_time, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def _items_for_type(
        self,
        record_type: str,
        *,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        status: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        if record_type == "qa":
            return self._qa_items(device_id, keyword, trace_id, manufacturer, product_series, date_from, date_to)
        if record_type == "diagnosis":
            return self._diagnosis_items(
                device_id,
                keyword,
                trace_id,
                fault_type,
                alarm_code,
                manufacturer,
                product_series,
                date_from,
                date_to,
            )
        if record_type == "task":
            return self._task_items(
                device_id,
                keyword,
                trace_id,
                status,
                fault_type,
                alarm_code,
                manufacturer,
                product_series,
                date_from,
                date_to,
            )
        if record_type == "maintenance_record":
            return self._maintenance_record_items(device_id, keyword, trace_id, fault_type, alarm_code, date_from, date_to)
        if record_type == "sop_execution":
            return self._sop_execution_items(device_id, keyword, status, date_from, date_to)
        if record_type == "knowledge_document":
            return self._knowledge_document_items(keyword, status, manufacturer, product_series, date_from, date_to)
        if record_type == "knowledge_contribution":
            return self._knowledge_contribution_items(
                device_id,
                keyword,
                trace_id,
                status,
                fault_type,
                alarm_code,
                manufacturer,
                product_series,
                date_from,
                date_to,
            )
        if record_type == "media":
            return self._media_items(device_id, keyword, trace_id, status, manufacturer, product_series, date_from, date_to)
        if record_type == "knowledge_graph_node":
            return self._kg_node_items(keyword, status, manufacturer, product_series, date_from, date_to)
        if record_type == "knowledge_graph_edge":
            return self._kg_edge_items(keyword, status, date_from, date_to)
        if record_type == "knowledge_graph_extraction_run":
            return self._kg_extraction_run_items(keyword, status, date_from, date_to)
        return []

    def _qa_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if device_id:
            filters.append(QARecord.device_id == device_id)
        if trace_id:
            filters.append(QARecord.trace_id.ilike(f"%{trace_id}%"))
        if manufacturer:
            filters.append(QARecord.manufacturer == manufacturer)
        if product_series:
            filters.append(QARecord.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(QARecord.question.ilike(pattern), QARecord.answer.ilike(pattern), QARecord.trace_id.ilike(pattern)))
        self._date_filters(filters, QARecord.created_at, date_from, date_to)
        records = self._fetch(QARecord, filters, QARecord.created_at.desc())
        return [self._item_from_record("qa", record) for record in records]

    def _diagnosis_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if device_id:
            filters.append(DiagnosisRecord.device_id == device_id)
        if trace_id:
            filters.append(DiagnosisRecord.trace_id.ilike(f"%{trace_id}%"))
        if fault_type:
            filters.append(DiagnosisRecord.fault_type == fault_type)
        if alarm_code:
            filters.append(DiagnosisRecord.alarm_code.ilike(f"%{alarm_code}%"))
        if manufacturer:
            filters.append(DiagnosisRecord.manufacturer == manufacturer)
        if product_series:
            filters.append(DiagnosisRecord.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    DiagnosisRecord.fault_description.ilike(pattern),
                    DiagnosisRecord.alarm_info.ilike(pattern),
                    DiagnosisRecord.device_name.ilike(pattern),
                    DiagnosisRecord.trace_id.ilike(pattern),
                )
            )
        self._date_filters(filters, DiagnosisRecord.created_at, date_from, date_to)
        records = self._fetch(DiagnosisRecord, filters, DiagnosisRecord.created_at.desc())
        return [self._item_from_record("diagnosis", record) for record in records]

    def _task_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        status: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if device_id:
            filters.append(MaintenanceTask.device_id == device_id)
        if trace_id:
            filters.append(MaintenanceTask.source_trace_id.ilike(f"%{trace_id}%"))
        if status:
            filters.append(or_(MaintenanceTask.status == status, MaintenanceTask.task_status == status))
        if fault_type:
            filters.append(MaintenanceTask.fault_type == fault_type)
        if alarm_code:
            filters.append(MaintenanceTask.alarm_code.ilike(f"%{alarm_code}%"))
        if manufacturer:
            filters.append(MaintenanceTask.manufacturer == manufacturer)
        if product_series:
            filters.append(MaintenanceTask.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    MaintenanceTask.title.ilike(pattern),
                    MaintenanceTask.device_name.ilike(pattern),
                    MaintenanceTask.fault_description.ilike(pattern),
                    MaintenanceTask.alarm_code.ilike(pattern),
                    MaintenanceTask.source_trace_id.ilike(pattern),
                )
            )
        self._date_filters(filters, MaintenanceTask.created_at, date_from, date_to)
        records = self._fetch(MaintenanceTask, filters, MaintenanceTask.created_at.desc())
        return [self._item_from_record("task", record) for record in records]

    def _maintenance_record_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if device_id:
            filters.append(DeviceMaintenanceRecord.device_id == device_id)
        if trace_id:
            filters.append(
                or_(
                    DeviceMaintenanceRecord.diagnosis_trace_id.ilike(f"%{trace_id}%"),
                    DeviceMaintenanceRecord.qa_trace_id.ilike(f"%{trace_id}%"),
                )
            )
        if fault_type:
            filters.append(DeviceMaintenanceRecord.fault_type == fault_type)
        if alarm_code:
            filters.append(DeviceMaintenanceRecord.alarm_code.ilike(f"%{alarm_code}%"))
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    DeviceMaintenanceRecord.fault_description.ilike(pattern),
                    DeviceMaintenanceRecord.root_cause.ilike(pattern),
                    DeviceMaintenanceRecord.repair_action.ilike(pattern),
                    DeviceMaintenanceRecord.verification_result.ilike(pattern),
                )
            )
        self._date_filters(filters, DeviceMaintenanceRecord.created_at, date_from, date_to)
        records = self._fetch(DeviceMaintenanceRecord, filters, DeviceMaintenanceRecord.created_at.desc())
        return [self._item_from_record("maintenance_record", record) for record in records]

    def _sop_execution_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        statement = (
            select(SOPExecutionRecord)
            .options(selectinload(SOPExecutionRecord.template), selectinload(SOPExecutionRecord.task))
            .order_by(SOPExecutionRecord.created_at.desc())
        )
        if device_id:
            task_ids = select(MaintenanceTask.id).where(MaintenanceTask.device_id == device_id)
            filters.append(SOPExecutionRecord.task_id.in_(task_ids))
        if status:
            filters.append(SOPExecutionRecord.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(SOPExecutionRecord.abnormal_notes.ilike(pattern))
        self._date_filters(filters, SOPExecutionRecord.created_at, date_from, date_to)
        if filters:
            statement = statement.where(*filters)
        records = list(self.db.scalars(statement))
        return [self._item_from_record("sop_execution", record) for record in records]

    def _knowledge_document_items(
        self,
        keyword: str | None,
        status: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if status:
            filters.append(or_(KnowledgeDocument.status == status, KnowledgeDocument.review_status == status))
        if manufacturer:
            filters.append(KnowledgeDocument.manufacturer == manufacturer)
        if product_series:
            filters.append(KnowledgeDocument.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.summary.ilike(pattern),
                    KnowledgeDocument.source.ilike(pattern),
                    KnowledgeDocument.file_name.ilike(pattern),
                )
            )
        self._date_filters(filters, KnowledgeDocument.created_at, date_from, date_to)
        records = self._fetch(KnowledgeDocument, filters, KnowledgeDocument.created_at.desc())
        return [self._item_from_record("knowledge_document", record) for record in records]

    def _media_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        status: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if device_id:
            filters.append(UploadedMedia.device_id == device_id)
        if trace_id:
            filters.append(UploadedMedia.qa_trace_id.ilike(f"%{trace_id}%"))
        if status:
            filters.append(UploadedMedia.status == status)
        if manufacturer:
            filters.append(UploadedMedia.manufacturer == manufacturer)
        if product_series:
            filters.append(UploadedMedia.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    UploadedMedia.file_name.ilike(pattern),
                    UploadedMedia.original_file_name.ilike(pattern),
                    UploadedMedia.description.ilike(pattern),
                    UploadedMedia.ocr_text.ilike(pattern),
                )
            )
        self._date_filters(filters, UploadedMedia.created_at, date_from, date_to)
        records = self._fetch(UploadedMedia, filters, UploadedMedia.created_at.desc())
        return [self._item_from_record("media", record) for record in records]

    def _knowledge_contribution_items(
        self,
        device_id: UUID | None,
        keyword: str | None,
        trace_id: str | None,
        status: str | None,
        fault_type: str | None,
        alarm_code: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if device_id:
            filters.append(KnowledgeContribution.device_id == device_id)
        if trace_id:
            filters.append(KnowledgeContribution.source_trace_id.ilike(f"%{trace_id}%"))
        if status:
            filters.append(KnowledgeContribution.review_status == status)
        if manufacturer:
            filters.append(KnowledgeContribution.manufacturer == manufacturer)
        if product_series:
            filters.append(KnowledgeContribution.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    KnowledgeContribution.title.ilike(pattern),
                    KnowledgeContribution.content.ilike(pattern),
                    KnowledgeContribution.source_trace_id.ilike(pattern),
                    KnowledgeContribution.review_comment.ilike(pattern),
                )
            )
        self._date_filters(filters, KnowledgeContribution.created_at, date_from, date_to)
        if fault_type or alarm_code:
            records = self._fetch(KnowledgeContribution, filters, KnowledgeContribution.created_at.desc())
            return [
                self._item_from_record("knowledge_contribution", record)
                for record in records
                if (not fault_type or self._metadata_value(record, "fault_type") == fault_type)
                and (not alarm_code or alarm_code.lower() in str(self._metadata_value(record, "alarm_code") or "").lower())
            ]
        records = self._fetch(KnowledgeContribution, filters, KnowledgeContribution.created_at.desc())
        return [self._item_from_record("knowledge_contribution", record) for record in records]

    def _kg_node_items(
        self,
        keyword: str | None,
        status: str | None,
        manufacturer: str | None,
        product_series: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if status:
            filters.append(KGNode.status == status)
        if manufacturer:
            filters.append(KGNode.manufacturer == manufacturer)
        if product_series:
            filters.append(KGNode.product_series == product_series)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(KGNode.canonical_name.ilike(pattern), KGNode.display_name.ilike(pattern), KGNode.node_type.ilike(pattern)))
        self._date_filters(filters, KGNode.created_at, date_from, date_to)
        records = self._fetch(KGNode, filters, KGNode.created_at.desc())
        return [self._item_from_record("knowledge_graph_node", record) for record in records]

    def _kg_edge_items(
        self,
        keyword: str | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if status:
            filters.append(KGEdge.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(KGEdge.relation_type.ilike(pattern), KGEdge.display_relation.ilike(pattern)))
        self._date_filters(filters, KGEdge.created_at, date_from, date_to)
        records = self._fetch(KGEdge, filters, KGEdge.created_at.desc())
        return [self._item_from_record("knowledge_graph_edge", record) for record in records]

    def _kg_extraction_run_items(
        self,
        keyword: str | None,
        status: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list[dict[str, Any]]:
        filters = []
        if status:
            filters.append(KGExtractionRun.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(or_(KGExtractionRun.source_type.ilike(pattern), KGExtractionRun.extractor.ilike(pattern), KGExtractionRun.error_summary.ilike(pattern)))
        self._date_filters(filters, KGExtractionRun.created_at, date_from, date_to)
        records = self._fetch(KGExtractionRun, filters, KGExtractionRun.created_at.desc())
        return [self._item_from_record("knowledge_graph_extraction_run", record) for record in records]

    def _item_from_record(self, record_type: str, record: Any) -> dict[str, Any]:
        device = self._device_for_record(record)
        created_by = self._operator_id_for_record(record_type, record)
        user = self.db.get(User, created_by) if created_by else None
        status = self._status_for_record(record_type, record)
        return {
            "record_type": record_type,
            "record_id": record.id,
            "trace_id": self._trace_for_record(record_type, record),
            "title": self._title_for_record(record_type, record),
            "summary": self._summary_for_record(record_type, record),
            "device_id": getattr(record, "device_id", None),
            "device_name": self._device_name_for_record(record, device),
            "status": status,
            "fault_type": self._fault_type_for_record(record_type, record),
            "alarm_code": self._alarm_code_for_record(record_type, record),
            "manufacturer": self._manufacturer_for_record(record, device),
            "product_series": self._product_series_for_record(record, device),
            "created_by_name": self._user_name(user),
            "created_at": getattr(record, "created_at", None),
        }

    def _related_records(self, *, record_type: str, record: Any) -> list[dict[str, Any]]:
        related: list[dict[str, Any]] = []
        device_id = getattr(record, "device_id", None)
        trace_id = self._trace_for_record(record_type, record)
        fault_type = self._fault_type_for_record(record_type, record)
        alarm_code = self._alarm_code_for_record(record_type, record)

        if device_id:
            related.extend(
                self.search(record_type="all", device_id=device_id, page=1, page_size=12)["items"]
            )
        if trace_id:
            related.extend(
                self.search(record_type="all", trace_id=trace_id, page=1, page_size=12)["items"]
            )
        if fault_type or alarm_code:
            related.extend(
                self.search(
                    record_type="all",
                    fault_type=fault_type,
                    alarm_code=alarm_code,
                    page=1,
                    page_size=12,
                )["items"]
            )

        if record_type == "knowledge_contribution":
            approved_document_id = getattr(record, "approved_document_id", None)
            if approved_document_id:
                document = self.db.get(KnowledgeDocument, approved_document_id)
                if document:
                    related.append(self._item_from_record("knowledge_document", document))
            metadata = record.metadata_json or {}
            related_task_id = metadata.get("related_task_id")
            if related_task_id:
                try:
                    task = self.db.get(MaintenanceTask, UUID(str(related_task_id)))
                except ValueError:
                    task = None
                if task:
                    related.append(self._item_from_record("task", task))
            related_diagnosis_trace_id = metadata.get("related_diagnosis_trace_id")
            if related_diagnosis_trace_id:
                diagnosis = self.db.scalar(
                    select(DiagnosisRecord).where(DiagnosisRecord.trace_id == str(related_diagnosis_trace_id))
                )
                if diagnosis:
                    related.append(self._item_from_record("diagnosis", diagnosis))

        seen = {str(getattr(record, "id", ""))}
        unique: list[dict[str, Any]] = []
        for item in related:
            key = str(item["record_id"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique[:12]

    def _media_for_record(self, *, record_type: str, record: Any) -> list[UploadedMedia]:
        filters = []
        if record_type == "media":
            return [record]
        if record_type == "diagnosis":
            media_ids = []
            for item in record.media_ids or []:
                try:
                    media_ids.append(UUID(str(item)))
                except ValueError:
                    continue
            filters.append(
                or_(
                    UploadedMedia.diagnosis_record_id == record.id,
                    UploadedMedia.id.in_(media_ids) if media_ids else UploadedMedia.id.is_(None),
                )
            )
        elif record_type == "qa":
            filters.append(UploadedMedia.qa_trace_id == record.trace_id)
        elif record_type == "task":
            conditions = [UploadedMedia.task_id == record.id]
            if record.source_type == "diagnosis" and record.source_trace_id:
                diagnosis = self.db.scalar(
                    select(DiagnosisRecord).where(DiagnosisRecord.trace_id == record.source_trace_id)
                )
                if diagnosis:
                    conditions.append(UploadedMedia.diagnosis_record_id == diagnosis.id)
            if record.source_type == "qa" and record.source_trace_id:
                conditions.append(UploadedMedia.qa_trace_id == record.source_trace_id)
            filters.append(or_(*conditions))
        elif record_type == "maintenance_record":
            conditions = []
            if record.task_id:
                conditions.append(UploadedMedia.task_id == record.task_id)
            if record.diagnosis_trace_id:
                diagnosis = self.db.scalar(
                    select(DiagnosisRecord).where(DiagnosisRecord.trace_id == record.diagnosis_trace_id)
                )
                if diagnosis:
                    conditions.append(UploadedMedia.diagnosis_record_id == diagnosis.id)
            if record.qa_trace_id:
                conditions.append(UploadedMedia.qa_trace_id == record.qa_trace_id)
            if conditions:
                filters.append(or_(*conditions))
        elif record_type == "sop_execution" and record.task_id:
            filters.append(UploadedMedia.task_id == record.task_id)
        elif record_type == "knowledge_contribution":
            media_ids = []
            for item in (record.metadata_json or {}).get("media_ids", []) or []:
                try:
                    media_ids.append(UUID(str(item)))
                except ValueError:
                    continue
            conditions = []
            if media_ids:
                conditions.append(UploadedMedia.id.in_(media_ids))
            if record.source_trace_id:
                conditions.append(UploadedMedia.qa_trace_id == record.source_trace_id)
            if conditions:
                filters.append(or_(*conditions))
        if not filters:
            return []
        statement = (
            select(UploadedMedia)
            .where(*filters)
            .order_by(UploadedMedia.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def _media_payload(self, media: UploadedMedia) -> dict[str, Any]:
        metadata = media.metadata_json or {}
        uploader = self.db.get(User, media.uploaded_by) if media.uploaded_by else None
        device = self.db.get(Device, media.device_id) if media.device_id else None
        return {
            "id": str(media.id),
            "file_name": media.file_name,
            "original_file_name": media.original_file_name,
            "file_ext": media.file_ext,
            "mime_type": media.mime_type,
            "file_size": media.file_size,
            "media_type": media.media_type,
            "description": media.description,
            "ocr_text": media.ocr_text,
            "manufacturer": media.manufacturer,
            "product_series": media.product_series,
            "device_type": media.device_type,
            "device_id": str(media.device_id) if media.device_id else None,
            "device_name": device.device_name if device else None,
            "task_id": str(media.task_id) if media.task_id else None,
            "fault_type": metadata.get("fault_type"),
            "alarm_code": metadata.get("alarm_code"),
            "ocr_status": metadata.get("ocr_status") or "disabled",
            "ocr_message": metadata.get("ocr_message") or "OCR service is not configured",
            "ocr_error_summary": metadata.get("ocr_error_summary"),
            "ocr_provider": (metadata.get("ocr") or {}).get("provider") if isinstance(metadata.get("ocr"), dict) else None,
            "ocr_lang": (metadata.get("ocr") or {}).get("lang") if isinstance(metadata.get("ocr"), dict) else None,
            "ocr_processed_at": metadata.get("ocr_processed_at"),
            "uploaded_by_name": self._user_name(uploader),
            "preview_url": f"/api/media/{media.id}/content",
            "created_at": media.created_at,
        }

    def _kg_context_for_record(self, record_type: str, record: Any) -> dict[str, Any]:
        related_history = getattr(record, "related_history", None) or []
        summaries = [
            item
            for item in related_history
            if isinstance(item, dict) and item.get("record_type") == "kg_context_summary"
        ]
        evidence: list[dict[str, Any]] = []
        if record_type == "diagnosis" and getattr(record, "trace_id", None):
            evidence = [
                self._kg_evidence_payload(item)
                for item in self.db.scalars(
                    select(KGEvidenceLink)
                    .where(KGEvidenceLink.diagnosis_trace_id == record.trace_id)
                    .order_by(KGEvidenceLink.created_at.desc())
                    .limit(20)
                )
            ]
        if record_type == "knowledge_graph_node":
            evidence = [
                self._kg_evidence_payload(item)
                for item in self.db.scalars(
                    select(KGEvidenceLink)
                    .where(KGEvidenceLink.node_id == record.id)
                    .order_by(KGEvidenceLink.created_at.desc())
                    .limit(20)
                )
            ]
        if record_type == "knowledge_graph_edge":
            evidence = [
                self._kg_evidence_payload(item)
                for item in self.db.scalars(
                    select(KGEvidenceLink)
                    .where(KGEvidenceLink.edge_id == record.id)
                    .order_by(KGEvidenceLink.created_at.desc())
                    .limit(20)
                )
            ]
        return {
            "summaries": summaries,
            "evidence": evidence,
            "has_context": bool(summaries or evidence),
        }

    @staticmethod
    def _kg_evidence_payload(item: KGEvidenceLink) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "node_id": str(item.node_id) if item.node_id else None,
            "edge_id": str(item.edge_id) if item.edge_id else None,
            "source_type": item.source_type,
            "source_id": str(item.source_id) if item.source_id else None,
            "document_id": str(item.document_id) if item.document_id else None,
            "chunk_id": str(item.chunk_id) if item.chunk_id else None,
            "contribution_id": str(item.contribution_id) if item.contribution_id else None,
            "diagnosis_trace_id": item.diagnosis_trace_id,
            "task_id": str(item.task_id) if item.task_id else None,
            "media_id": str(item.media_id) if item.media_id else None,
            "evidence_text": item.evidence_text,
            "confidence": item.confidence,
            "created_at": item.created_at,
        }

    def _fetch(self, model: Any, filters: list[Any], order_by: Any) -> list[Any]:
        statement = select(model).order_by(order_by)
        if filters:
            statement = statement.where(*filters)
        return list(self.db.scalars(statement))

    def _count(self, model: Any, *filters: Any) -> int:
        statement = select(func.count()).select_from(model)
        if filters:
            statement = statement.where(*filters)
        return self.db.scalar(statement) or 0

    @staticmethod
    def _date_filters(filters: list[Any], column: Any, date_from: datetime | None, date_to: datetime | None) -> None:
        if date_from:
            filters.append(column >= date_from)
        if date_to:
            filters.append(column <= date_to)

    @staticmethod
    def _model_for_type(record_type: str) -> Any | None:
        return {
            "qa": QARecord,
            "diagnosis": DiagnosisRecord,
            "task": MaintenanceTask,
            "maintenance_record": DeviceMaintenanceRecord,
            "sop_execution": SOPExecutionRecord,
            "knowledge_document": KnowledgeDocument,
            "knowledge_contribution": KnowledgeContribution,
            "media": UploadedMedia,
            "knowledge_graph_node": KGNode,
            "knowledge_graph_edge": KGEdge,
            "knowledge_graph_extraction_run": KGExtractionRun,
        }.get(record_type)

    def _device_for_record(self, record: Any) -> Device | None:
        device = getattr(record, "device", None)
        if device:
            return device
        device_id = getattr(record, "device_id", None)
        if device_id:
            return self.db.get(Device, device_id)
        task_id = getattr(record, "task_id", None)
        if task_id:
            task = self.db.get(MaintenanceTask, task_id)
            if task and task.device_id:
                return self.db.get(Device, task.device_id)
        return None

    @staticmethod
    def _operator_id_for_record(record_type: str, record: Any) -> UUID | None:
        if record_type in {"qa", "diagnosis", "task"}:
            return getattr(record, "created_by", None)
        if record_type == "maintenance_record":
            return getattr(record, "completed_by", None)
        if record_type == "sop_execution":
            return getattr(record, "executor_id", None)
        if record_type == "knowledge_document":
            return getattr(record, "submitted_by", None)
        if record_type == "knowledge_contribution":
            return getattr(record, "submitted_by", None)
        if record_type == "media":
            return getattr(record, "uploaded_by", None)
        if record_type in {"knowledge_graph_node", "knowledge_graph_edge", "knowledge_graph_extraction_run"}:
            return getattr(record, "created_by", None)
        return None

    @staticmethod
    def _trace_for_record(record_type: str, record: Any) -> str | None:
        if record_type in {"qa", "diagnosis"}:
            return getattr(record, "trace_id", None)
        if record_type == "task":
            return getattr(record, "source_trace_id", None)
        if record_type == "maintenance_record":
            return getattr(record, "diagnosis_trace_id", None) or getattr(record, "qa_trace_id", None)
        if record_type == "media":
            return getattr(record, "qa_trace_id", None)
        if record_type == "knowledge_contribution":
            return getattr(record, "source_trace_id", None)
        if record_type == "knowledge_graph_extraction_run":
            return str(getattr(record, "id", "")) or None
        return None

    @staticmethod
    def _status_for_record(record_type: str, record: Any) -> str | None:
        if record_type in {"knowledge_document", "knowledge_contribution"}:
            return getattr(record, "review_status", None) or getattr(record, "status", None)
        return getattr(record, "status", None) or getattr(record, "task_status", None)

    @staticmethod
    def _title_for_record(record_type: str, record: Any) -> str:
        if record_type == "qa":
            return f"检修问答：{record.question[:48]}"
        if record_type == "diagnosis":
            return f"故障诊断：{(record.fault_description or record.alarm_code or '诊断记录')[:48]}"
        if record_type == "task":
            return record.title
        if record_type == "maintenance_record":
            return f"维修履历：{(record.fault_type or record.alarm_code or '设备处理记录')}"
        if record_type == "sop_execution":
            template = getattr(record, "template", None)
            return f"SOP 执行：{template.title if template else record.template_id}"
        if record_type == "knowledge_document":
            return record.title
        if record_type == "knowledge_contribution":
            return f"知识贡献：{record.title}"
        if record_type == "media":
            return record.original_file_name or record.file_name
        if record_type == "knowledge_graph_node":
            return f"知识图谱节点：{record.display_name or record.canonical_name}"
        if record_type == "knowledge_graph_edge":
            return f"知识图谱关系：{record.display_relation or record.relation_type}"
        if record_type == "knowledge_graph_extraction_run":
            return f"图谱抽取运行：{record.source_type}"
        return str(record.id)

    @staticmethod
    def _summary_for_record(record_type: str, record: Any) -> str | None:
        if record_type == "qa":
            return record.answer[:180] if record.answer else None
        if record_type == "diagnosis":
            return record.alarm_info or record.device_status or record.fault_description
        if record_type == "task":
            return record.fault_description or record.result_summary
        if record_type == "maintenance_record":
            return record.repair_action or record.root_cause or record.verification_result
        if record_type == "sop_execution":
            return record.abnormal_notes
        if record_type == "knowledge_document":
            return record.summary or record.source
        if record_type == "knowledge_contribution":
            return record.content[:180] if record.content else None
        if record_type == "media":
            return record.description
        if record_type == "knowledge_graph_node":
            return f"{record.node_type} / {record.manufacturer or '-'} / {record.product_series or '-'}"
        if record_type == "knowledge_graph_edge":
            return f"{record.relation_type} / evidence={record.evidence_count}"
        if record_type == "knowledge_graph_extraction_run":
            return record.error_summary or f"candidate_count={record.candidate_count}"
        return None

    @staticmethod
    def _metadata_value(record: Any, key: str) -> Any:
        metadata = getattr(record, "metadata_json", None) or {}
        return metadata.get(key)

    def _fault_type_for_record(self, record_type: str, record: Any) -> str | None:
        value = getattr(record, "fault_type", None)
        if value:
            return value
        if record_type == "knowledge_contribution":
            return self._metadata_value(record, "fault_type")
        return None

    def _alarm_code_for_record(self, record_type: str, record: Any) -> str | None:
        value = getattr(record, "alarm_code", None)
        if value:
            return value
        if record_type == "knowledge_contribution":
            return self._metadata_value(record, "alarm_code")
        return None

    @staticmethod
    def _manufacturer_for_record(record: Any, device: Device | None) -> str | None:
        return getattr(record, "manufacturer", None) or getattr(device, "manufacturer", None)

    @staticmethod
    def _product_series_for_record(record: Any, device: Device | None) -> str | None:
        return getattr(record, "product_series", None) or getattr(device, "product_series", None)

    @staticmethod
    def _device_name_for_record(record: Any, device: Device | None) -> str | None:
        return getattr(record, "device_name", None) or getattr(device, "device_name", None)

    @staticmethod
    def _user_name(user: User | None) -> str | None:
        if not user:
            return None
        return user.display_name or user.username

    @staticmethod
    def _record_dict(record: Any) -> dict[str, Any]:
        mapper = inspect(record).mapper
        return {column.key: getattr(record, column.key) for column in mapper.column_attrs}
