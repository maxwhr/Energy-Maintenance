from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import QARecord, UploadedMedia, User
from app.repositories.qa_record_repository import QARecordRepository
from app.schemas.retrieval import RetrievalQueryRequest, RetrievalQueryResponse
from app.services.media_service import MediaService
from app.services.retrieval_pipeline_context import RetrievalPipelineError
from app.services.retrieval_response_builder import RetrievalResponseBuilder


class RetrievalPersistenceService:
    """Persist retrieval results only when requested, with trace-level idempotency."""

    def __init__(
        self,
        db: Session,
        *,
        qa_repository: QARecordRepository,
        media_service: MediaService,
    ) -> None:
        self.db = db
        self.qa_repository = qa_repository
        self.media_service = media_service

    def persist_if_requested(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
        media_items: list[UploadedMedia],
    ) -> bool:
        if not payload.persist_result:
            return False
        if self.qa_repository.get_by_trace_id(response.trace_id):
            return False
        self._save_qa_record(response, payload, current_user, media_items)
        return True

    def _save_qa_record(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
        media_items: list[UploadedMedia],
    ) -> None:
        stored_history = [
            item.model_dump(mode="json") for item in response.related_history
        ]
        stored_history.extend(
            {
                "record_type": "media_context",
                **item.model_dump(mode="json"),
            }
            for item in response.media_items
        )
        stored_history.extend(
            {
                "record_type": "ocr_context",
                **item,
            }
            for item in response.ocr_context
        )
        if response.kg_context:
            stored_history.append(
                {
                    "record_type": "kg_context_summary",
                    **RetrievalResponseBuilder.kg_context_summary(response.kg_context),
                }
            )
        stored_history.append(
            {
                "record_type": "retrieval_diagnostics",
                "retrieval_mode": response.retrieval_mode,
                "vector_backend": response.vector_backend,
                "vector_available": response.vector_available,
                "hybrid_used": response.hybrid_used,
                "vector_fallback_used": response.vector_fallback_used,
                "embedding_provider": response.embedding_provider,
                "embedding_model": response.embedding_model,
                "diagnostics": response.retrieval_diagnostics,
            }
        )
        record = QARecord(
            trace_id=response.trace_id,
            device_id=payload.device_id,
            question=response.question,
            normalized_query=response.question,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            document_type=payload.document_type,
            answer=response.answer,
            references=[
                item.model_dump(mode="json") for item in response.references
            ],
            retrieved_chunks=[
                item.model_dump(mode="json") for item in response.retrieved_chunks
            ],
            suggested_steps=response.suggested_steps,
            safety_notes=response.safety_notes,
            related_history=stored_history,
            model_provider=response.model_provider,
            model_name=response.model_name,
            confidence=response.confidence,
            created_by=current_user.id,
        )
        try:
            self.qa_repository.create_qa_record(record)
            self.media_service.link_to_qa(media_items, response.trace_id)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise RetrievalPipelineError(f"QA record write failed: {exc}") from exc
