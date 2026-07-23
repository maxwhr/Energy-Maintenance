from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy import String, and_, cast, exists, false, func, literal, null, or_, select, union_all
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Session, load_only, raiseload

from app.models import (
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KGEdge,
    KGExtractionRun,
    KGNode,
    KnowledgeContribution,
    KnowledgeDocument,
    MaintenanceTask,
    MaintenanceWorkflow,
    ModelOutputCorrection,
    QARecord,
    SOPExecutionRecord,
    SOPTemplate,
    UploadedMedia,
    User,
)
from app.schemas.record_center import RecordCenterItemIdentity, RecordCenterRecordType


RECORD_TYPE_ORDER = (
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
)

_KG_RUN_TEST_SOURCE_PREFIX = re.compile(r"^task(?:21|22|24|25)[a-z]*_r\d+_", re.IGNORECASE)


def kg_extraction_run_display_source(value: str, record_id: UUID) -> str:
    normalized = _KG_RUN_TEST_SOURCE_PREFIX.sub("", value).strip(" _-")
    return normalized or f"历史业务记录-{str(record_id)[:8]}"


class RecordCenterQueryRepository:
    """Bounded Record Center query plan: identity page, batch loads, in-memory assembly."""

    def __init__(self, db: Session):
        self.db = db

    def overview(self) -> dict[str, Any]:
        counts = self.aggregate_overview_counts()
        recent = self.search(record_type="all", page=1, page_size=8)["items"]
        return {**counts, "recent_records": recent}

    def search(
        self,
        *,
        record_type: str = "all",
        device_id: UUID | None = None,
        workflow_id: str | None = None,
        actor_id: UUID | None = None,
        keyword: str | None = None,
        trace_id: str | None = None,
        status: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort_direction: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        types = RECORD_TYPE_ORDER if record_type == "all" else (record_type,)
        filters = {
            "device_id": device_id,
            "workflow_id": workflow_id,
            "actor_id": actor_id,
            "keyword": keyword,
            "trace_id": trace_id,
            "status": status,
            "fault_type": fault_type,
            "alarm_code": alarm_code,
            "manufacturer": manufacturer,
            "product_series": product_series,
            "date_from": date_from,
            "date_to": date_to,
        }
        identity_union = union_all(
            *(self._identity_select(current_type, filters) for current_type in types)
        ).subquery("record_center_identity")
        total = int(self.db.scalar(select(func.count()).select_from(identity_union)) or 0)
        ordering = (
            identity_union.c.primary_timestamp.asc()
            if sort_direction == "asc"
            else identity_union.c.primary_timestamp.desc()
        )
        statement = (
            select(identity_union)
            .order_by(
                ordering,
                identity_union.c.source_priority.asc(),
                identity_union.c.record_type.asc(),
                identity_union.c.record_id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        identities = [RecordCenterItemIdentity.model_validate(dict(row)) for row in self.db.execute(statement).mappings()]
        items = self._assemble_page(identities)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def aggregate_overview_counts(self) -> dict[str, int]:
        sources = (
            ("qa_records", QARecord),
            ("diagnosis_records", DiagnosisRecord),
            ("maintenance_tasks", MaintenanceTask),
            ("maintenance_records", DeviceMaintenanceRecord),
            ("sop_executions", SOPExecutionRecord),
            ("knowledge_documents", KnowledgeDocument),
            ("knowledge_contributions", KnowledgeContribution),
            ("uploaded_media", UploadedMedia),
            ("devices", Device),
            ("knowledge_graph_nodes", KGNode),
            ("knowledge_graph_edges", KGEdge),
            ("knowledge_graph_extraction_runs", KGExtractionRun),
        )
        statement = union_all(
            *(
                select(literal(name).label("metric"), func.count().label("value")).select_from(model)
                for name, model in sources
            )
        )
        return {str(metric): int(value) for metric, value in self.db.execute(statement).all()}

    def _identity_select(self, record_type: str, values: dict[str, Any]):
        model, device_column, actor_column, status_column, title_key, summary_key = self._identity_spec(record_type)
        created_at = model.created_at
        updated_at = getattr(model, "updated_at", created_at)
        workflow_expression = self._workflow_expression(record_type, model)
        conditions = self._filters_for_type(record_type, values)
        return select(
            cast(literal(record_type), String).label("record_type"),
            model.id.label("record_id"),
            created_at.label("primary_timestamp"),
            updated_at.label("secondary_timestamp"),
            (device_column if device_column is not None else cast(null(), PGUUID(as_uuid=True))).label("device_id"),
            cast(workflow_expression, String).label("workflow_id"),
            (actor_column if actor_column is not None else cast(null(), PGUUID(as_uuid=True))).label("actor_id"),
            cast(status_column, String).label("status"),
            cast(literal(title_key), String).label("title_key"),
            cast(literal(summary_key), String).label("summary_key"),
            cast(literal(model.__tablename__), String).label("source_table"),
            literal(RECORD_TYPE_ORDER.index(record_type)).label("source_priority"),
        ).select_from(model).where(*conditions)

    @staticmethod
    def _identity_spec(record_type: str) -> tuple[Any, Any, Any, Any, str, str | None]:
        specs = {
            "qa": (QARecord, QARecord.device_id, QARecord.created_by, cast(null(), String), "question", "answer"),
            "diagnosis": (DiagnosisRecord, DiagnosisRecord.device_id, DiagnosisRecord.created_by, cast(null(), String), "fault_description", "alarm_info"),
            "task": (MaintenanceTask, MaintenanceTask.device_id, MaintenanceTask.created_by, func.coalesce(MaintenanceTask.status, MaintenanceTask.task_status), "title", "fault_description"),
            "maintenance_record": (DeviceMaintenanceRecord, DeviceMaintenanceRecord.device_id, DeviceMaintenanceRecord.completed_by, cast(null(), String), "fault_type", "repair_action"),
            "sop_execution": (SOPExecutionRecord, None, SOPExecutionRecord.executor_id, SOPExecutionRecord.status, "template_id", "abnormal_notes"),
            "knowledge_document": (KnowledgeDocument, None, KnowledgeDocument.submitted_by, func.coalesce(KnowledgeDocument.review_status, KnowledgeDocument.status), "title", "summary"),
            "knowledge_contribution": (KnowledgeContribution, KnowledgeContribution.device_id, KnowledgeContribution.submitted_by, KnowledgeContribution.review_status, "title", "content"),
            "media": (UploadedMedia, UploadedMedia.device_id, UploadedMedia.uploaded_by, UploadedMedia.status, "original_file_name", "description"),
            "knowledge_graph_node": (KGNode, None, KGNode.created_by, KGNode.status, "display_name", "node_type"),
            "knowledge_graph_edge": (KGEdge, None, KGEdge.created_by, KGEdge.status, "display_relation", "relation_type"),
            "knowledge_graph_extraction_run": (KGExtractionRun, None, KGExtractionRun.created_by, KGExtractionRun.status, "source_type", "error_summary"),
        }
        return specs[record_type]

    @staticmethod
    def _workflow_expression(record_type: str, model: Any):
        condition = None
        if record_type == "diagnosis":
            condition = MaintenanceWorkflow.diagnosis_id == model.id
        elif record_type == "task":
            condition = MaintenanceWorkflow.formal_task_id == model.id
        elif record_type == "maintenance_record":
            condition = MaintenanceWorkflow.record_id == model.id
        elif record_type == "sop_execution":
            condition = MaintenanceWorkflow.formal_task_id == model.task_id
        if condition is None:
            return cast(null(), String)
        return (
            select(MaintenanceWorkflow.workflow_id)
            .where(condition)
            .order_by(MaintenanceWorkflow.created_at.desc(), MaintenanceWorkflow.id.asc())
            .limit(1)
            .scalar_subquery()
        )

    def _filters_for_type(self, record_type: str, values: dict[str, Any]) -> list[Any]:
        model, _device, actor, _status, _title, _summary = self._identity_spec(record_type)
        conditions: list[Any] = []
        keyword = values["keyword"]
        trace_id = values["trace_id"]
        status = values["status"]
        device_id = values["device_id"]
        manufacturer = values["manufacturer"]
        product_series = values["product_series"]
        fault_type = values["fault_type"]
        alarm_code = values["alarm_code"]

        if values["date_from"]:
            conditions.append(model.created_at >= values["date_from"])
        if values["date_to"]:
            conditions.append(model.created_at <= values["date_to"])
        if values["actor_id"]:
            conditions.append(actor == values["actor_id"] if actor is not None else false())
        if values["workflow_id"]:
            conditions.append(self._workflow_filter(record_type, model, values["workflow_id"]))

        if record_type == "qa":
            self._append_direct_filters(conditions, QARecord, device_id, manufacturer, product_series)
            if trace_id:
                conditions.append(QARecord.trace_id.ilike(f"%{trace_id}%"))
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(QARecord.question.ilike(pattern), QARecord.answer.ilike(pattern), QARecord.trace_id.ilike(pattern)))
        elif record_type == "diagnosis":
            self._append_direct_filters(conditions, DiagnosisRecord, device_id, manufacturer, product_series)
            if trace_id:
                conditions.append(DiagnosisRecord.trace_id.ilike(f"%{trace_id}%"))
            if fault_type:
                conditions.append(DiagnosisRecord.fault_type == fault_type)
            if alarm_code:
                conditions.append(DiagnosisRecord.alarm_code.ilike(f"%{alarm_code}%"))
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(DiagnosisRecord.fault_description.ilike(pattern), DiagnosisRecord.alarm_info.ilike(pattern), DiagnosisRecord.device_name.ilike(pattern), DiagnosisRecord.trace_id.ilike(pattern)))
        elif record_type == "task":
            self._append_direct_filters(conditions, MaintenanceTask, device_id, manufacturer, product_series)
            if trace_id:
                conditions.append(MaintenanceTask.source_trace_id.ilike(f"%{trace_id}%"))
            if status:
                conditions.append(or_(MaintenanceTask.status == status, MaintenanceTask.task_status == status))
            if fault_type:
                conditions.append(MaintenanceTask.fault_type == fault_type)
            if alarm_code:
                conditions.append(MaintenanceTask.alarm_code.ilike(f"%{alarm_code}%"))
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(MaintenanceTask.title.ilike(pattern), MaintenanceTask.device_name.ilike(pattern), MaintenanceTask.fault_description.ilike(pattern), MaintenanceTask.alarm_code.ilike(pattern), MaintenanceTask.source_trace_id.ilike(pattern)))
        elif record_type == "maintenance_record":
            if device_id:
                conditions.append(DeviceMaintenanceRecord.device_id == device_id)
            if trace_id:
                conditions.append(or_(DeviceMaintenanceRecord.diagnosis_trace_id.ilike(f"%{trace_id}%"), DeviceMaintenanceRecord.qa_trace_id.ilike(f"%{trace_id}%")))
            if fault_type:
                conditions.append(DeviceMaintenanceRecord.fault_type == fault_type)
            if alarm_code:
                conditions.append(DeviceMaintenanceRecord.alarm_code.ilike(f"%{alarm_code}%"))
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(DeviceMaintenanceRecord.fault_description.ilike(pattern), DeviceMaintenanceRecord.root_cause.ilike(pattern), DeviceMaintenanceRecord.repair_action.ilike(pattern), DeviceMaintenanceRecord.verification_result.ilike(pattern)))
        elif record_type == "sop_execution":
            if device_id:
                conditions.append(SOPExecutionRecord.task_id.in_(select(MaintenanceTask.id).where(MaintenanceTask.device_id == device_id)))
            if status:
                conditions.append(SOPExecutionRecord.status == status)
            if keyword:
                conditions.append(SOPExecutionRecord.abnormal_notes.ilike(f"%{keyword}%"))
        elif record_type == "knowledge_document":
            if status:
                conditions.append(or_(KnowledgeDocument.status == status, KnowledgeDocument.review_status == status))
            if manufacturer:
                conditions.append(KnowledgeDocument.manufacturer == manufacturer)
            if product_series:
                conditions.append(KnowledgeDocument.product_series == product_series)
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(KnowledgeDocument.title.ilike(pattern), KnowledgeDocument.summary.ilike(pattern), KnowledgeDocument.source.ilike(pattern), KnowledgeDocument.file_name.ilike(pattern)))
        elif record_type == "knowledge_contribution":
            self._append_direct_filters(conditions, KnowledgeContribution, device_id, manufacturer, product_series)
            if trace_id:
                conditions.append(KnowledgeContribution.source_trace_id.ilike(f"%{trace_id}%"))
            if status:
                conditions.append(KnowledgeContribution.review_status == status)
            if fault_type:
                conditions.append(KnowledgeContribution.metadata_json["fault_type"].astext == fault_type)
            if alarm_code:
                conditions.append(KnowledgeContribution.metadata_json["alarm_code"].astext.ilike(f"%{alarm_code}%"))
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(KnowledgeContribution.title.ilike(pattern), KnowledgeContribution.content.ilike(pattern), KnowledgeContribution.source_trace_id.ilike(pattern), KnowledgeContribution.review_comment.ilike(pattern)))
        elif record_type == "media":
            self._append_direct_filters(conditions, UploadedMedia, device_id, manufacturer, product_series)
            if trace_id:
                conditions.append(UploadedMedia.qa_trace_id.ilike(f"%{trace_id}%"))
            if status:
                conditions.append(UploadedMedia.status == status)
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(UploadedMedia.file_name.ilike(pattern), UploadedMedia.original_file_name.ilike(pattern), UploadedMedia.description.ilike(pattern), UploadedMedia.ocr_text.ilike(pattern)))
        elif record_type == "knowledge_graph_node":
            if status:
                conditions.append(KGNode.status == status)
            if manufacturer:
                conditions.append(KGNode.manufacturer == manufacturer)
            if product_series:
                conditions.append(KGNode.product_series == product_series)
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(KGNode.canonical_name.ilike(pattern), KGNode.display_name.ilike(pattern), KGNode.node_type.ilike(pattern)))
        elif record_type == "knowledge_graph_edge":
            if status:
                conditions.append(KGEdge.status == status)
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(KGEdge.relation_type.ilike(pattern), KGEdge.display_relation.ilike(pattern)))
        elif record_type == "knowledge_graph_extraction_run":
            if status:
                conditions.append(KGExtractionRun.status == status)
            if keyword:
                pattern = f"%{keyword}%"
                conditions.append(or_(KGExtractionRun.source_type.ilike(pattern), KGExtractionRun.extractor.ilike(pattern), KGExtractionRun.error_summary.ilike(pattern)))
        return conditions

    @staticmethod
    def _append_direct_filters(conditions: list[Any], model: Any, device_id: UUID | None, manufacturer: str | None, product_series: str | None) -> None:
        if device_id:
            conditions.append(model.device_id == device_id)
        if manufacturer:
            conditions.append(model.manufacturer == manufacturer)
        if product_series:
            conditions.append(model.product_series == product_series)

    @staticmethod
    def _workflow_filter(record_type: str, model: Any, workflow_id: str):
        if record_type == "diagnosis":
            link = MaintenanceWorkflow.diagnosis_id == model.id
        elif record_type == "task":
            link = MaintenanceWorkflow.formal_task_id == model.id
        elif record_type == "maintenance_record":
            link = MaintenanceWorkflow.record_id == model.id
        elif record_type == "sop_execution":
            link = MaintenanceWorkflow.formal_task_id == model.task_id
        else:
            return false()
        return exists(select(MaintenanceWorkflow.id).where(link, MaintenanceWorkflow.workflow_id == workflow_id))

    def _assemble_page(self, identities: list[RecordCenterItemIdentity]) -> list[dict[str, Any]]:
        if not identities:
            return []
        ids_by_type: dict[str, set[UUID]] = defaultdict(set)
        for identity in identities:
            ids_by_type[identity.record_type.value].add(identity.record_id)
        records_by_type = {
            record_type: self._get_records_by_ids(record_type, ids)
            for record_type, ids in ids_by_type.items()
        }

        sop_records = records_by_type.get("sop_execution", {})
        task_ids = {record.task_id for record in sop_records.values() if record.task_id}
        tasks_by_id = dict(records_by_type.get("task", {}))
        missing_task_ids = task_ids - set(tasks_by_id)
        tasks_by_id.update(self.get_tasks_by_ids(missing_task_ids))
        template_ids = {record.template_id for record in sop_records.values() if record.template_id}
        templates_by_id = self.get_sops_by_ids(template_ids)

        device_ids = {identity.device_id for identity in identities if identity.device_id}
        device_ids.update(task.device_id for task in tasks_by_id.values() if task.device_id)
        devices_by_id = self.get_devices_by_ids(device_ids)
        users_by_id = self.get_users_by_ids({identity.actor_id for identity in identities if identity.actor_id})

        output = []
        for identity in identities:
            record = records_by_type.get(identity.record_type.value, {}).get(identity.record_id)
            if record is None:
                continue
            output.append(
                self._item_from_loaded(
                    identity.record_type.value,
                    record,
                    devices_by_id=devices_by_id,
                    users_by_id=users_by_id,
                    tasks_by_id=tasks_by_id,
                    templates_by_id=templates_by_id,
                )
            )
        return output

    def _get_records_by_ids(self, record_type: str, ids: Iterable[UUID]) -> dict[UUID, Any]:
        identifiers = set(ids)
        if not identifiers:
            return {}
        model, columns = self._page_load_spec(record_type)
        statement = select(model).options(load_only(*columns), raiseload("*")).where(model.id.in_(identifiers))
        return {record.id: record for record in self.db.scalars(statement)}

    @staticmethod
    def _page_load_spec(record_type: str) -> tuple[Any, tuple[Any, ...]]:
        specs = {
            "qa": (QARecord, (QARecord.id, QARecord.question, QARecord.answer, QARecord.device_id, QARecord.manufacturer, QARecord.product_series, QARecord.trace_id, QARecord.created_by, QARecord.created_at)),
            "diagnosis": (DiagnosisRecord, (DiagnosisRecord.id, DiagnosisRecord.fault_description, DiagnosisRecord.alarm_code, DiagnosisRecord.alarm_info, DiagnosisRecord.device_status, DiagnosisRecord.device_name, DiagnosisRecord.fault_type, DiagnosisRecord.manufacturer, DiagnosisRecord.product_series, DiagnosisRecord.device_id, DiagnosisRecord.trace_id, DiagnosisRecord.created_by, DiagnosisRecord.created_at)),
            "task": (MaintenanceTask, (MaintenanceTask.id, MaintenanceTask.title, MaintenanceTask.manufacturer, MaintenanceTask.product_series, MaintenanceTask.device_id, MaintenanceTask.device_name, MaintenanceTask.fault_type, MaintenanceTask.alarm_code, MaintenanceTask.fault_description, MaintenanceTask.result_summary, MaintenanceTask.status, MaintenanceTask.task_status, MaintenanceTask.source_trace_id, MaintenanceTask.created_by, MaintenanceTask.created_at)),
            "maintenance_record": (DeviceMaintenanceRecord, (DeviceMaintenanceRecord.id, DeviceMaintenanceRecord.device_id, DeviceMaintenanceRecord.task_id, DeviceMaintenanceRecord.diagnosis_trace_id, DeviceMaintenanceRecord.qa_trace_id, DeviceMaintenanceRecord.fault_type, DeviceMaintenanceRecord.alarm_code, DeviceMaintenanceRecord.fault_description, DeviceMaintenanceRecord.root_cause, DeviceMaintenanceRecord.repair_action, DeviceMaintenanceRecord.verification_result, DeviceMaintenanceRecord.completed_by, DeviceMaintenanceRecord.created_at)),
            "sop_execution": (SOPExecutionRecord, (SOPExecutionRecord.id, SOPExecutionRecord.task_id, SOPExecutionRecord.template_id, SOPExecutionRecord.executor_id, SOPExecutionRecord.abnormal_notes, SOPExecutionRecord.status, SOPExecutionRecord.created_at)),
            "knowledge_document": (KnowledgeDocument, (KnowledgeDocument.id, KnowledgeDocument.title, KnowledgeDocument.summary, KnowledgeDocument.source, KnowledgeDocument.manufacturer, KnowledgeDocument.product_series, KnowledgeDocument.status, KnowledgeDocument.review_status, KnowledgeDocument.submitted_by, KnowledgeDocument.created_at)),
            "knowledge_contribution": (KnowledgeContribution, (KnowledgeContribution.id, KnowledgeContribution.title, KnowledgeContribution.content, KnowledgeContribution.manufacturer, KnowledgeContribution.product_series, KnowledgeContribution.device_id, KnowledgeContribution.source_trace_id, KnowledgeContribution.review_status, KnowledgeContribution.submitted_by, KnowledgeContribution.metadata_json, KnowledgeContribution.created_at)),
            "media": (UploadedMedia, (UploadedMedia.id, UploadedMedia.file_name, UploadedMedia.original_file_name, UploadedMedia.description, UploadedMedia.manufacturer, UploadedMedia.product_series, UploadedMedia.device_id, UploadedMedia.qa_trace_id, UploadedMedia.status, UploadedMedia.uploaded_by, UploadedMedia.created_at)),
            "knowledge_graph_node": (KGNode, (KGNode.id, KGNode.node_type, KGNode.canonical_name, KGNode.display_name, KGNode.manufacturer, KGNode.product_series, KGNode.status, KGNode.created_by, KGNode.created_at)),
            "knowledge_graph_edge": (KGEdge, (KGEdge.id, KGEdge.relation_type, KGEdge.display_relation, KGEdge.evidence_count, KGEdge.status, KGEdge.created_by, KGEdge.created_at)),
            "knowledge_graph_extraction_run": (KGExtractionRun, (KGExtractionRun.id, KGExtractionRun.source_type, KGExtractionRun.candidate_count, KGExtractionRun.error_summary, KGExtractionRun.status, KGExtractionRun.created_by, KGExtractionRun.created_at)),
        }
        return specs[record_type]

    def get_users_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, dict[str, Any]]:
        identifiers = set(ids)
        if not identifiers:
            return {}
        rows = self.db.execute(select(User.id, User.username, User.display_name).where(User.id.in_(identifiers)))
        return {row.id: {"id": row.id, "username": row.username, "display_name": row.display_name} for row in rows}

    def get_devices_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, dict[str, Any]]:
        identifiers = set(ids)
        if not identifiers:
            return {}
        rows = self.db.execute(select(Device.id, Device.device_name, Device.manufacturer, Device.product_series).where(Device.id.in_(identifiers)))
        return {row.id: {"id": row.id, "device_name": row.device_name, "manufacturer": row.manufacturer, "product_series": row.product_series} for row in rows}

    def get_workflows_by_ids(self, ids: Iterable[str]) -> dict[str, MaintenanceWorkflow]:
        identifiers = set(ids)
        if not identifiers:
            return {}
        rows = self.db.scalars(select(MaintenanceWorkflow).options(raiseload("*")).where(MaintenanceWorkflow.workflow_id.in_(identifiers)))
        return {row.workflow_id: row for row in rows}

    def get_tasks_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, MaintenanceTask]:
        return self._get_records_by_ids("task", ids)

    def get_media_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, UploadedMedia]:
        return self._get_records_by_ids("media", ids)

    def get_corrections_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, ModelOutputCorrection]:
        identifiers = set(ids)
        if not identifiers:
            return {}
        rows = self.db.scalars(select(ModelOutputCorrection).options(raiseload("*")).where(ModelOutputCorrection.id.in_(identifiers)))
        return {row.id: row for row in rows}

    def get_diagnoses_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, DiagnosisRecord]:
        return self._get_records_by_ids("diagnosis", ids)

    def get_sops_by_ids(self, ids: Iterable[UUID]) -> dict[UUID, dict[str, Any]]:
        identifiers = set(ids)
        if not identifiers:
            return {}
        rows = self.db.execute(select(SOPTemplate.id, SOPTemplate.title).where(SOPTemplate.id.in_(identifiers)))
        return {row.id: {"id": row.id, "title": row.title} for row in rows}

    @staticmethod
    def _item_from_loaded(
        record_type: str,
        record: Any,
        *,
        devices_by_id: dict[UUID, dict[str, Any]],
        users_by_id: dict[UUID, dict[str, Any]],
        tasks_by_id: dict[UUID, MaintenanceTask],
        templates_by_id: dict[UUID, dict[str, Any]],
    ) -> dict[str, Any]:
        task = tasks_by_id.get(getattr(record, "task_id", None))
        resolved_device_id = getattr(record, "device_id", None) or getattr(task, "device_id", None)
        device = devices_by_id.get(resolved_device_id)
        actor_id = RecordCenterQueryRepository._operator_id(record_type, record)
        user = users_by_id.get(actor_id)
        return {
            "record_type": record_type,
            "record_id": record.id,
            "trace_id": RecordCenterQueryRepository._trace(record_type, record),
            "title": RecordCenterQueryRepository._title(record_type, record, templates_by_id),
            "summary": RecordCenterQueryRepository._summary(record_type, record),
            "device_id": getattr(record, "device_id", None),
            "device_name": getattr(record, "device_name", None) or (device or {}).get("device_name"),
            "status": RecordCenterQueryRepository._status(record_type, record),
            "fault_type": RecordCenterQueryRepository._fault_type(record_type, record),
            "alarm_code": RecordCenterQueryRepository._alarm_code(record_type, record),
            "manufacturer": getattr(record, "manufacturer", None) or (device or {}).get("manufacturer"),
            "product_series": getattr(record, "product_series", None) or (device or {}).get("product_series"),
            "created_by_name": ((user or {}).get("display_name") or (user or {}).get("username")),
            "created_at": getattr(record, "created_at", None),
        }

    @staticmethod
    def _operator_id(record_type: str, record: Any) -> UUID | None:
        mapping = {
            "qa": "created_by", "diagnosis": "created_by", "task": "created_by",
            "maintenance_record": "completed_by", "sop_execution": "executor_id",
            "knowledge_document": "submitted_by", "knowledge_contribution": "submitted_by",
            "media": "uploaded_by", "knowledge_graph_node": "created_by",
            "knowledge_graph_edge": "created_by", "knowledge_graph_extraction_run": "created_by",
        }
        return getattr(record, mapping[record_type], None)

    @staticmethod
    def _trace(record_type: str, record: Any) -> str | None:
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
            return str(record.id)
        return None

    @staticmethod
    def _status(record_type: str, record: Any) -> str | None:
        if record_type in {"knowledge_document", "knowledge_contribution"}:
            return getattr(record, "review_status", None) or getattr(record, "status", None)
        return getattr(record, "status", None) or getattr(record, "task_status", None)

    @staticmethod
    def _title(record_type: str, record: Any, templates: dict[UUID, dict[str, Any]]) -> str:
        if record_type == "qa":
            return f"检修问答：{record.question[:48]}"
        if record_type == "diagnosis":
            return f"故障诊断：{(record.fault_description or record.alarm_code or '诊断记录')[:48]}"
        if record_type == "task":
            return record.title
        if record_type == "maintenance_record":
            return f"维修履历：{record.fault_type or record.alarm_code or '设备处理记录'}"
        if record_type == "sop_execution":
            template = templates.get(record.template_id)
            return f"SOP 执行：{template['title'] if template else record.template_id}"
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
            return f"图谱抽取运行：{kg_extraction_run_display_source(record.source_type, record.id)}"
        return str(record.id)

    @staticmethod
    def _summary(record_type: str, record: Any) -> str | None:
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
    def _fault_type(record_type: str, record: Any) -> str | None:
        value = getattr(record, "fault_type", None)
        if value:
            return value
        if record_type == "knowledge_contribution":
            return (record.metadata_json or {}).get("fault_type")
        return None

    @staticmethod
    def _alarm_code(record_type: str, record: Any) -> str | None:
        value = getattr(record, "alarm_code", None)
        if value:
            return value
        if record_type == "knowledge_contribution":
            return (record.metadata_json or {}).get("alarm_code")
        return None
