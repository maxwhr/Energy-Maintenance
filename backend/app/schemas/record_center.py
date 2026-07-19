from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


RecordType = Literal[
    "all",
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


class RecordCenterRecordType(str, Enum):
    QA = "qa"
    DIAGNOSIS = "diagnosis"
    TASK = "task"
    MAINTENANCE_RECORD = "maintenance_record"
    SOP_EXECUTION = "sop_execution"
    KNOWLEDGE_DOCUMENT = "knowledge_document"
    KNOWLEDGE_CONTRIBUTION = "knowledge_contribution"
    MEDIA = "media"
    KNOWLEDGE_GRAPH_NODE = "knowledge_graph_node"
    KNOWLEDGE_GRAPH_EDGE = "knowledge_graph_edge"
    KNOWLEDGE_GRAPH_EXTRACTION_RUN = "knowledge_graph_extraction_run"


class RecordCenterItemIdentity(BaseModel):
    record_type: RecordCenterRecordType
    record_id: UUID
    primary_timestamp: datetime
    secondary_timestamp: datetime | None = None
    device_id: UUID | None = None
    workflow_id: str | None = None
    actor_id: UUID | None = None
    status: str | None = None
    title_key: str
    summary_key: str | None = None
    source_table: str
    source_priority: int


class RecordCenterItem(BaseModel):
    record_type: str
    record_id: UUID | str
    trace_id: str | None = None
    title: str
    summary: str | None = None
    device_id: UUID | None = None
    device_name: str | None = None
    status: str | None = None
    fault_type: str | None = None
    alarm_code: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    created_by_name: str | None = None
    created_at: datetime | None = None


class RecordCenterOverview(BaseModel):
    qa_records: int = 0
    diagnosis_records: int = 0
    maintenance_tasks: int = 0
    maintenance_records: int = 0
    sop_executions: int = 0
    knowledge_documents: int = 0
    knowledge_contributions: int = 0
    uploaded_media: int = 0
    devices: int = 0
    recent_records: list[RecordCenterItem] = Field(default_factory=list)


class RecordCenterPage(BaseModel):
    items: list[RecordCenterItem]
    total: int
    page: int
    page_size: int


class RecordCenterDetail(BaseModel):
    record_type: str
    record_id: UUID | str
    record: dict[str, Any]
    related_records: list[RecordCenterItem] = Field(default_factory=list)


class DeviceTimelineItem(BaseModel):
    time: datetime | None = None
    record_type: str
    title: str
    summary: str | None = None
    trace_id: str | None = None
    record_id: UUID | str
    status: str | None = None
    operator_name: str | None = None


class DeviceTimelineResponse(BaseModel):
    device: dict[str, Any]
    timeline: list[DeviceTimelineItem]
