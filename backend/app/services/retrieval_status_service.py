from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.retrieval_lab_config import get_retrieval_lab_settings
from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    QARecord,
    VectorIndexRun,
)


class RetrievalStatusService:
    """Collect production retrieval state without consulting lab artifacts."""

    SUPPORTED_MANUFACTURERS = ("huawei", "sungrow")

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def collect(self) -> dict:
        approved_documents = int(
            self.db.scalar(
                select(func.count(KnowledgeDocument.id)).where(
                    KnowledgeDocument.status == "active",
                    KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.review_status == "approved",
                    KnowledgeDocument.manufacturer.in_(self.SUPPORTED_MANUFACTURERS),
                )
            )
            or 0
        )
        approved_chunks = int(
            self.db.scalar(
                select(func.count(KnowledgeChunk.id))
                .join(
                    KnowledgeDocument,
                    KnowledgeDocument.id == KnowledgeChunk.document_id,
                )
                .where(
                    KnowledgeChunk.status == "active",
                    KnowledgeDocument.status == "active",
                    KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.review_status == "approved",
                    KnowledgeDocument.manufacturer.in_(self.SUPPORTED_MANUFACTURERS),
                )
            )
            or 0
        )
        latest_index = self.db.scalar(
            select(VectorIndexRun)
            .where(
                (VectorIndexRun.namespace.is_(None))
                | (VectorIndexRun.namespace.in_(("", "default")))
            )
            .order_by(VectorIndexRun.created_at.desc())
            .limit(1)
        )
        citation_total, citation_valid = self._citation_counts()

        provider_keys = (
            self.settings.CLOUD_LLM_API_KEY,
            self.settings.CLOUD_VISION_API_KEY,
            self.settings.OCR_API_KEY,
            self.settings.EMBEDDING_API_KEY,
            self.settings.RERANK_API_KEY,
            self.settings.DASHVECTOR_API_KEY,
            self.settings.DASHSCOPE_API_KEY,
            self.settings.MIMO_API_KEY,
            self.settings.MINIMAX_API_KEY,
        )
        rerank_enabled = bool(
            self.settings.RERANK_ENABLED
            or self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED
            or self.settings.RAG_DEDICATED_RERANK_ENABLED
        )
        return {
            "default_strategy": self.settings.RETRIEVAL_DEFAULT_MODE,
            "recommended_strategy": self.settings.RETRIEVAL_DEFAULT_MODE,
            "fallback_strategy": "keyword",
            "fallback_reason": "controlled_evidence_fallback",
            "manufacturers": list(self.SUPPORTED_MANUFACTURERS),
            "approved_active_document_count": approved_documents,
            "approved_active_chunk_count": approved_chunks,
            "citation_validity_rate": (
                round(citation_valid / citation_total, 4) if citation_total else 0.0
            ),
            "citation_count": citation_total,
            "valid_citation_count": citation_valid,
            "controlled_refusal_enabled": True,
            "vector_enabled": bool(
                self.settings.VECTOR_SEARCH_ENABLED
                and self.settings.DASHVECTOR_ENABLED
            ),
            "embedding_enabled": bool(self.settings.EMBEDDING_ENABLED),
            "rerank_enabled": rerank_enabled,
            "external_provider_configured": any(
                bool(value and value.strip()) for value in provider_keys
            ),
            "external_real_calls_enabled": bool(
                self.settings.EXTERNAL_REAL_CALLS_ENABLED
            ),
            "latest_formal_index": {
                "status": latest_index.status if latest_index else "not_run",
                "backend": latest_index.vector_backend if latest_index else None,
                "finished_at": (
                    latest_index.finished_at.isoformat()
                    if latest_index and latest_index.finished_at
                    else None
                ),
            },
            "lab_enabled": bool(
                get_retrieval_lab_settings().ENABLE_RETRIEVAL_LAB
            ),
        }

    def _citation_counts(self) -> tuple[int, int]:
        references: list[dict] = []
        for stored in self.db.scalars(select(QARecord.references)):
            if isinstance(stored, list):
                references.extend(item for item in stored if isinstance(item, dict))

        parsed: list[tuple[dict, UUID]] = []
        chunk_ids: set[UUID] = set()
        for reference in references:
            try:
                chunk_id = UUID(str(reference.get("chunk_id")))
            except (TypeError, ValueError):
                continue
            parsed.append((reference, chunk_id))
            chunk_ids.add(chunk_id)

        valid_pairs: set[tuple[str, str]] = set()
        if chunk_ids:
            rows = self.db.execute(
                select(KnowledgeChunk.id, KnowledgeDocument.id)
                .join(
                    KnowledgeDocument,
                    KnowledgeDocument.id == KnowledgeChunk.document_id,
                )
                .where(
                    KnowledgeChunk.id.in_(chunk_ids),
                    KnowledgeChunk.status == "active",
                    KnowledgeDocument.status == "active",
                    KnowledgeDocument.parse_status == "parsed",
                    KnowledgeDocument.review_status == "approved",
                )
            )
            valid_pairs = {
                (str(chunk_id), str(document_id))
                for chunk_id, document_id in rows
            }

        valid = sum(
            (str(chunk_id), str(reference.get("document_id"))) in valid_pairs
            for reference, chunk_id in parsed
        )
        return len(references), valid
