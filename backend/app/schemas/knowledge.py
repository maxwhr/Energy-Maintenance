from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeDocumentBase(BaseModel):
    title: str
    manufacturer: str
    product_series: str | None = None
    model: str | None = None
    device_type: str = "pv_inverter"
    document_type: str = "manual"
    source: str | None = None
    source_type: str = "user_upload"
    file_name: str | None = None
    file_path: str | None = None
    file_size: int | None = None
    file_ext: str | None = None
    page_count: int | None = None
    parse_status: str = "pending"
    parser_name: str | None = None
    chunk_count: int = 0
    summary: str | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] | None = None
    parsed_at: datetime | None = None
    review_status: str = "draft"
    submitted_by: UUID | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    status: str = "active"


class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    pass


class KnowledgeDocumentRead(KnowledgeDocumentBase):
    id: UUID
    original_file_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocumentRead]
    total: int
    page: int
    page_size: int


class KnowledgeDocumentDetail(KnowledgeDocumentRead):
    pass


class KnowledgeDocumentUploadResponse(BaseModel):
    document_id: UUID
    title: str
    status: str
    parse_status: str
    review_status: str
    chunk_count: int
    file_name: str | None = None
    original_file_name: str | None = None
    warnings: list[str] = Field(default_factory=list)


class KnowledgeChunkBase(BaseModel):
    document_id: UUID
    manufacturer: str
    product_series: str | None = None
    device_type: str = "pv_inverter"
    document_type: str
    chunk_index: int
    content: str
    content_hash: str | None = None
    section_title: str | None = None
    char_count: int = 0
    page_number: int | None = None
    embedding_status: str = "pending"
    metadata_json: dict[str, Any] | None = None
    status: str = "active"


class KnowledgeChunkRead(KnowledgeChunkBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeChunkCreate(KnowledgeChunkBase):
    pass


class KnowledgeChunkListResponse(BaseModel):
    items: list[KnowledgeChunkRead]
    total: int
    page: int
    page_size: int


class ParsedDocumentPage(BaseModel):
    page_number: int | None = None
    text: str


class ParsedDocument(BaseModel):
    text: str
    pages: list[ParsedDocumentPage] = Field(default_factory=list)
    page_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class TextChunk(BaseModel):
    chunk_index: int
    content: str
    section_title: str | None = None
    char_count: int
    page_number: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
