from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NODE_TYPES = {
    "manufacturer",
    "product_series",
    "device_model",
    "device",
    "fault",
    "alarm",
    "component",
    "symptom",
    "cause",
    "inspection_item",
    "action",
    "tool",
    "part",
    "safety_risk",
    "sop_template",
    "sop_step",
    "knowledge_document",
    "knowledge_chunk",
    "maintenance_task",
    "maintenance_record",
    "media_evidence",
    "contribution",
}

RELATION_TYPES = {
    "BELONGS_TO",
    "HAS_MODEL",
    "HAS_DEVICE",
    "HAS_FAULT",
    "HAS_ALARM",
    "HAS_SYMPTOM",
    "CAUSED_BY",
    "CHECK_BY",
    "RESOLVED_BY",
    "USES_TOOL",
    "REQUIRES_PART",
    "HAS_SAFETY_RISK",
    "GUIDED_BY_SOP",
    "HAS_STEP",
    "EVIDENCED_BY",
    "MENTIONED_IN",
    "DERIVED_FROM",
    "RECURRENT_WITH",
    "RELATED_TO",
}


class PageResult(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int


class KGNodeBase(BaseModel):
    node_type: str
    canonical_name: str = Field(min_length=1, max_length=255)
    display_name: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str = "pv_inverter"
    properties_json: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    status: str = "active"
    source_type: str | None = None
    source_id: UUID | None = None

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        if value not in NODE_TYPES:
            raise ValueError("Unsupported knowledge graph node_type")
        return value


class KGNodeCreate(KGNodeBase):
    aliases: list[str] = Field(default_factory=list)


class KGNodeUpdate(BaseModel):
    canonical_name: str | None = Field(default=None, min_length=1, max_length=255)
    display_name: str | None = None
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = None
    properties_json: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: str | None = None
    aliases: list[str] | None = None


class KGNodeRead(KGNodeBase):
    id: UUID
    created_by: UUID | None = None
    aliases: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KGNodeMergeRequest(BaseModel):
    target_node_id: UUID
    merge_alias: bool = True
    archive_source: bool = True
    comment: str | None = None


class KGEdgeBase(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    relation_type: str
    display_relation: str | None = None
    properties_json: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_count: int = 0
    status: str = "active"
    source_type: str | None = None
    source_id: UUID | None = None

    @field_validator("relation_type")
    @classmethod
    def validate_relation_type(cls, value: str) -> str:
        if value not in RELATION_TYPES:
            raise ValueError("Unsupported knowledge graph relation_type")
        return value


class KGEdgeCreate(KGEdgeBase):
    evidence_text: str | None = None


class KGEdgeUpdate(BaseModel):
    relation_type: str | None = None
    display_relation: str | None = None
    properties_json: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: str | None = None

    @field_validator("relation_type")
    @classmethod
    def validate_optional_relation_type(cls, value: str | None) -> str | None:
        if value is not None and value not in RELATION_TYPES:
            raise ValueError("Unsupported knowledge graph relation_type")
        return value


class KGEdgeRead(KGEdgeBase):
    id: UUID
    source_node_name: str | None = None
    target_node_name: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KGEvidenceRead(BaseModel):
    id: UUID
    node_id: UUID | None = None
    edge_id: UUID | None = None
    source_type: str
    source_id: UUID | None = None
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    contribution_id: UUID | None = None
    diagnosis_trace_id: str | None = None
    task_id: UUID | None = None
    maintenance_record_id: UUID | None = None
    media_id: UUID | None = None
    evidence_text: str | None = None
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KGExtractionRunRead(BaseModel):
    id: UUID
    source_type: str
    source_id: UUID | None = None
    extractor: str
    status: str
    candidate_count: int
    approved_count: int
    rejected_count: int
    error_summary: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_by: UUID | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KGCandidateRead(BaseModel):
    id: UUID
    run_id: UUID
    candidate_type: Literal["node", "edge", "alias"]
    payload_json: dict[str, Any]
    status: str
    confidence: float
    evidence_text: str | None = None
    approved_node_id: UUID | None = None
    approved_edge_id: UUID | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KGCandidateReviewRequest(BaseModel):
    comment: str | None = None


class KGExtractionRequest(BaseModel):
    max_chunks: int = Field(default=80, ge=1, le=500)
    dry_run: bool = False


class KGPathQuery(BaseModel):
    source_node_id: UUID
    target_node_id: UUID
    max_depth: int = Field(default=3, ge=1, le=5)


class KGOverview(BaseModel):
    node_count: int
    edge_count: int
    evidence_count: int
    pending_candidate_count: int
    completed_run_count: int
    node_type_counts: dict[str, int]
    relation_type_counts: dict[str, int]
    recent_runs: list[KGExtractionRunRead]


class KGNeighborhood(BaseModel):
    center: KGNodeRead
    nodes: list[KGNodeRead]
    edges: list[KGEdgeRead]


class KGPathResult(BaseModel):
    found: bool
    nodes: list[KGNodeRead] = Field(default_factory=list)
    edges: list[KGEdgeRead] = Field(default_factory=list)


class KGGraphResponse(BaseModel):
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    legend: dict[str, Any] = Field(default_factory=dict)


class KGSearchResponse(BaseModel):
    keyword: str | None = None
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class KGBusinessContextResponse(BaseModel):
    matched_nodes: list[dict[str, Any]] = Field(default_factory=list)
    related_faults: list[dict[str, Any]] = Field(default_factory=list)
    related_alarms: list[dict[str, Any]] = Field(default_factory=list)
    related_causes: list[dict[str, Any]] = Field(default_factory=list)
    inspection_items: list[dict[str, Any]] = Field(default_factory=list)
    recommended_actions: list[dict[str, Any]] = Field(default_factory=list)
    safety_risks: list[dict[str, Any]] = Field(default_factory=list)
    related_sop: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    parts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    graph_paths: list[dict[str, Any]] = Field(default_factory=list)
    kg_nodes: list[dict[str, Any]] = Field(default_factory=list)
    kg_edges: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class KGExtractionResult(BaseModel):
    run: KGExtractionRunRead
    candidates: list[KGCandidateRead]


class KGEvidenceCreate(BaseModel):
    node_id: UUID | None = None
    edge_id: UUID | None = None
    source_type: str
    source_id: UUID | None = None
    document_id: UUID | None = None
    chunk_id: UUID | None = None
    contribution_id: UUID | None = None
    diagnosis_trace_id: str | None = None
    task_id: UUID | None = None
    maintenance_record_id: UUID | None = None
    media_id: UUID | None = None
    evidence_text: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_target(self) -> "KGEvidenceCreate":
        if not self.node_id and not self.edge_id:
            raise ValueError("Evidence must point to either node_id or edge_id")
        return self
