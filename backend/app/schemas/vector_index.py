from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VectorSearchStatus(BaseModel):
    vector_search_enabled: bool
    vector_backend: str
    dashvector_enabled: bool
    dashvector_configured: bool
    dashvector_collection: str
    dashvector_namespace: str | None = None
    dashvector_dimension: int
    embedding_enabled: bool
    embedding_configured: bool
    embedding_provider: str
    embedding_model: str | None = None
    embedding_dimension: int
    deterministic_test_enabled: bool
    fake_adapter_available: bool
    real_adapter_available: bool
    status: Literal["available", "blocked", "error"]
    blocked_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VectorIndexRunRead(BaseModel):
    id: UUID
    run_type: str
    target_type: str
    target_id: UUID | None = None
    vector_backend: str
    collection_name: str
    namespace: str | None = None
    embedding_model: str
    embedding_provider: str
    status: str
    total_count: int
    succeeded_count: int
    failed_count: int
    skipped_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkVectorIndexRead(BaseModel):
    id: UUID
    chunk_id: UUID
    document_id: UUID | None = None
    vector_backend: str
    collection_name: str
    namespace: str | None = None
    vector_id: str
    embedding_model: str
    embedding_provider: str
    embedding_dim: int
    content_hash: str
    index_status: str
    last_indexed_at: datetime | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVectorIndexStatus(BaseModel):
    document_id: UUID
    chunk_count: int
    indexed_count: int
    stale_count: int
    failed_count: int
    indexes: list[ChunkVectorIndexRead] = Field(default_factory=list)


class IndexRequest(BaseModel):
    provider: str | None = None
    vector_backend: str | None = None
    force: bool = False


class ReindexStaleRequest(BaseModel):
    provider: str | None = None
    vector_backend: str | None = None
    limit: int = Field(default=200, ge=1, le=1000)


class VectorIndexJobResponse(BaseModel):
    run: VectorIndexRunRead
    processed: int
    succeeded: int
    skipped: int
    failed: int
    vector_backend: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    warnings: list[str] = Field(default_factory=list)


class VectorTestQueryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    provider: str | None = None
    vector_backend: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    manufacturer: str | None = None
    product_series: str | None = None
    device_type: str | None = "pv_inverter"
    document_type: str | None = None


class VectorTestQueryHit(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    chunk_index: int
    section_title: str | None = None
    vector_score: float
    vector_backend: str
    vector_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorTestQueryResponse(BaseModel):
    vector_backend: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    vector_available: bool
    hits: list[VectorTestQueryHit] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
