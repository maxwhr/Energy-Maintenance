from __future__ import annotations

import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import User
from app.repositories.qa_record_repository import QARecordRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.record import QARecordRead
from app.schemas.retrieval import (
    ALLOWED_DEVICE_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_MANUFACTURERS,
    ALLOWED_PRODUCT_SERIES,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
)
from app.schemas.retrieval_scope import (
    CHINESE_ENGINEERING_PILOT_SCOPE_ID,
    HUAWEI_SUN2000_COMPETITION_SCOPE_ID,
    SUNGROW_SG_FORMAL_SCOPE_ID,
)
from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.answer_generation_service import AnswerGenerationService
from app.services.citation_validation_service import CitationValidationService
from app.services.media_service import MediaService, MediaServiceError
from app.services.model_prompt_builder import ModelPromptBuilder
from app.services.query_expansion_service import QueryExpansionService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.query_understanding_service import QueryUnderstandingService
from app.services.retrieval_candidate_coordinator import (
    RetrievalCandidateCoordinator,
)
from app.services.retrieval_evidence_gate import RetrievalEvidenceGate
from app.services.retrieval_persistence_service import RetrievalPersistenceService
from app.services.retrieval_pipeline_context import (
    RetrievalPipelineContext,
    RetrievalPipelineError,
)
from app.services.retrieval_response_builder import RetrievalResponseBuilder
from app.services.retrieval_scope_service import RetrievalScopeError, RetrievalScopeService


RetrievalServiceError = RetrievalPipelineError


class RetrievalService:
    """Orchestrate the typed retrieval pipeline and expose record queries."""

    def __init__(
        self,
        db: Session,
        *,
        allow_real_api: bool | None = None,
        vector_collection: str | None = None,
        vector_namespace: str | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.allow_real_api = (
            self.settings.TASK25B_ALLOW_REAL_API
            if allow_real_api is None
            else allow_real_api
        )
        self.vector_collection = vector_collection
        self.vector_namespace = vector_namespace
        self.repository = RetrievalRepository(db)
        self.qa_repository = QARecordRepository(db)
        self.expansion_service = QueryExpansionService()
        self.answer_service = AnswerGenerationService()
        self.prompt_builder = ModelPromptBuilder()
        self.media_service = MediaService(db)
        self.query_understanding_service = QueryUnderstandingService()
        self.citation_service = CitationValidationService(db)
        self.strategy_router = AdaptiveRetrievalStrategy()
        self.scope_service = RetrievalScopeService(db)
        self.candidate_coordinator = RetrievalCandidateCoordinator(
            db,
            repository=self.repository,
            settings=self.settings,
            query_understanding_service=self.query_understanding_service,
            allow_real_api=self.allow_real_api,
            vector_collection=self.vector_collection,
            vector_namespace=self.vector_namespace,
        )
        self.evidence_gate = RetrievalEvidenceGate(
            settings=self.settings,
            citation_service=self.citation_service,
        )
        self.response_builder = RetrievalResponseBuilder(
            db,
            repository=self.repository,
            media_service=self.media_service,
            answer_service=self.answer_service,
            prompt_builder=self.prompt_builder,
            settings=self.settings,
            vector_collection=self.vector_collection,
            vector_namespace=self.vector_namespace,
        )
        self.persistence_service = RetrievalPersistenceService(
            db,
            qa_repository=self.qa_repository,
            media_service=self.media_service,
        )

    def query(
        self,
        payload: RetrievalQueryRequest,
        current_user: User,
    ) -> RetrievalQueryResponse:
        self._validate_request(payload)
        resolved_request = self._resolve_retrieval_scope(
            self._resolve_device_context(payload)
        )
        unsupported_scope_reason = QuerySignalExtractionService.unsupported_scope_reason(
            resolved_request.normalized_question,
            manufacturer=resolved_request.manufacturer,
            product_series=resolved_request.product_series,
        )
        if unsupported_scope_reason:
            raise RetrievalServiceError(
                QuerySignalExtractionService.FORMAL_SUPPORT_MESSAGE
            )
        try:
            retrieval_scope = self.scope_service.resolve(
                resolved_request.scope_id,
                pilot_required=False,
            )
        except RetrievalScopeError as exc:
            raise RetrievalServiceError(str(exc)) from exc
        quality_gate_status = (
            "DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED"
            if retrieval_scope
            and retrieval_scope.scope_id == CHINESE_ENGINEERING_PILOT_SCOPE_ID
            else self.settings.RETRIEVAL_QUALITY_GATE_STATUS
        )
        try:
            media_items = self.media_service.resolve_media_items(
                resolved_request.media_ids,
                device_id=resolved_request.device_id,
            )
        except MediaServiceError as exc:
            raise RetrievalServiceError(str(exc)) from exc

        search_request = self._payload_with_media_context(
            resolved_request,
            media_items,
        )
        query_started = time.perf_counter()
        understanding_started = query_started
        understanding = self.query_understanding_service.understand(
            search_request.normalized_question
        )
        query_understanding_ms = (time.perf_counter() - understanding_started) * 1000
        decision = self.strategy_router.route(
            understanding,
            requested_strategy=resolved_request.retrieval_mode,
            reranker_enabled=self.settings.RETRIEVAL_FEATURE_RERANK_ENABLED,
        )
        expansion = self.expansion_service.expand(search_request)
        expansion.keywords = list(
            dict.fromkeys([*expansion.keywords, *understanding.expanded_terms])
        )
        context = RetrievalPipelineContext(
            request=payload,
            resolved_request=resolved_request,
            search_request=search_request,
            retrieval_scope=retrieval_scope,
            query_understanding=understanding,
            expansion=expansion,
            strategy_decision=decision,
            quality_gate_status=quality_gate_status,
            media_items=media_items,
            query_started=query_started,
            actual_strategy=decision.actual_strategy,
            latency_breakdown={"query_understanding": query_understanding_ms},
        )
        self.candidate_coordinator.retrieve(context)
        self.evidence_gate.apply(context)
        response = self.response_builder.build(context, current_user)
        self.persistence_service.persist_if_requested(
            response,
            resolved_request,
            current_user,
            media_items,
        )
        return response

    def list_records(
        self,
        *,
        device_id: UUID | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        records, total = self.qa_repository.list_qa_records(
            device_id=device_id,
            manufacturer=manufacturer,
            product_series=product_series,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [
                QARecordRead.model_validate(record).model_dump(mode="json")
                for record in records
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_record_detail(self, trace_id: str) -> dict | None:
        record = self.qa_repository.get_by_trace_id(trace_id)
        if not record:
            return None
        return QARecordRead.model_validate(record).model_dump(mode="json")

    @staticmethod
    def _validate_request(payload: RetrievalQueryRequest) -> None:
        if not payload.normalized_question:
            raise RetrievalServiceError("query or question must not be empty")
        if payload.top_k < 1 or payload.top_k > 10:
            raise RetrievalServiceError("top_k must be between 1 and 10")
        if payload.vector_top_k < 1 or payload.vector_top_k > 50:
            raise RetrievalServiceError("vector_top_k must be between 1 and 50")
        if payload.retrieval_mode not in {
            "keyword",
            "vector",
            "hybrid",
            "hybrid_rerank",
            "adaptive",
        }:
            raise RetrievalServiceError("unsupported retrieval_mode")
        if payload.hybrid_keyword_weight < 0 or payload.hybrid_vector_weight < 0:
            raise RetrievalServiceError("hybrid weights must be non-negative")
        if payload.hybrid_keyword_weight + payload.hybrid_vector_weight <= 0:
            raise RetrievalServiceError("hybrid weights must not both be zero")
        if payload.min_score < 0 or payload.min_score > 1:
            raise RetrievalServiceError("min_score must be between 0 and 1")
        if payload.manufacturer and payload.manufacturer not in ALLOWED_MANUFACTURERS:
            raise RetrievalServiceError("manufacturer must be huawei or sungrow")
        if payload.product_series and payload.product_series not in ALLOWED_PRODUCT_SERIES:
            raise RetrievalServiceError("unsupported product_series")
        if payload.device_type not in ALLOWED_DEVICE_TYPES:
            raise RetrievalServiceError("device_type must be pv_inverter")
        if payload.document_type and payload.document_type not in ALLOWED_DOCUMENT_TYPES:
            raise RetrievalServiceError("unsupported document_type")
        if len(payload.media_ids) > 10:
            raise RetrievalServiceError("media_ids supports at most 10 media items")

    def _resolve_device_context(
        self,
        payload: RetrievalQueryRequest,
    ) -> RetrievalQueryRequest:
        if not payload.device_id:
            return payload
        device = self.repository.get_device(payload.device_id)
        if not device:
            raise RetrievalServiceError("Device not found")
        update_data = payload.model_dump()
        update_data["manufacturer"] = payload.manufacturer or device.manufacturer
        update_data["product_series"] = (
            payload.product_series or device.product_series
        )
        update_data["device_type"] = payload.device_type or device.device_type
        return RetrievalQueryRequest(**update_data)

    @staticmethod
    def _resolve_retrieval_scope(
        payload: RetrievalQueryRequest,
    ) -> RetrievalQueryRequest:
        signals = QuerySignalExtractionService().extract(
            payload.normalized_question
        )
        manufacturer = payload.manufacturer or signals.manufacturer
        product_series = payload.product_series or signals.product_family

        if manufacturer is None:
            if product_series == "SG":
                manufacturer = "sungrow"
            elif product_series in {"SUN2000", "FusionSolar"}:
                manufacturer = "huawei"
        if product_series is None:
            product_series = "SG" if manufacturer == "sungrow" else "SUN2000"
        if manufacturer is None:
            manufacturer = "huawei"

        scope_id = payload.scope_id
        if scope_id is None:
            scope_id = (
                SUNGROW_SG_FORMAL_SCOPE_ID
                if manufacturer == "sungrow"
                else HUAWEI_SUN2000_COMPETITION_SCOPE_ID
            )
        elif (
            scope_id == HUAWEI_SUN2000_COMPETITION_SCOPE_ID
            and manufacturer == "sungrow"
        ):
            scope_id = SUNGROW_SG_FORMAL_SCOPE_ID

        return payload.model_copy(
            update={
                "manufacturer": manufacturer,
                "product_series": product_series,
                "scope_id": scope_id,
                "device_type": "pv_inverter",
            }
        )

    def _payload_with_media_context(
        self,
        payload: RetrievalQueryRequest,
        media_items: list,
    ) -> RetrievalQueryRequest:
        media_texts = self.media_service.media_context_texts(
            media_items,
            include_ocr_text=payload.use_ocr_text,
        )
        if not media_texts:
            return payload
        data = payload.model_dump()
        data["query"] = None
        data["question"] = "\n".join(
            [payload.normalized_question, *media_texts]
        )
        return RetrievalQueryRequest(**data)

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise RetrievalServiceError(
                "page must be greater than or equal to 1"
            )
        if page_size < 1 or page_size > 100:
            raise RetrievalServiceError(
                "page_size must be between 1 and 100"
            )
