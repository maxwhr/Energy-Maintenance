from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DeviceMaintenanceRecord, KnowledgeChunk, KnowledgeDocument, QARecord, User
from app.repositories.qa_record_repository import QARecordRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.record import QARecordRead
from app.schemas.retrieval import (
    ALLOWED_DEVICE_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_MANUFACTURERS,
    ALLOWED_PRODUCT_SERIES,
    RelatedHistoryItem,
    RetrievalQueryAnalysis,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
    RetrievalReference,
    RetrievedChunk,
)
from app.services.answer_generation_service import AnswerGenerationService
from app.services.hybrid_retrieval_service import HybridRetrievalService, HybridScoredCandidate
from app.services.media_service import MediaService, MediaServiceError
from app.services.model_enhancement_service import ModelEnhancementService
from app.services.model_prompt_builder import ModelPromptBuilder
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.query_expansion_service import QueryExpansionService
from app.services.vector_index_service import VectorIndexService


MODEL_PROVIDER = "rule_based"
MODEL_NAME = "keyword_retrieval_v1"


class RetrievalServiceError(ValueError):
    pass


@dataclass
class RetrievalQueryContext:
    response: RetrievalQueryResponse
    payload: RetrievalQueryRequest
    media_items: list


class RetrievalService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = RetrievalRepository(db)
        self.qa_repository = QARecordRepository(db)
        self.expansion_service = QueryExpansionService()
        self.answer_service = AnswerGenerationService()
        self.prompt_builder = ModelPromptBuilder()
        self.media_service = MediaService(db)

    def query(self, payload: RetrievalQueryRequest, current_user: User) -> RetrievalQueryResponse:
        self._validate_request(payload)
        resolved_payload = self._resolve_device_context(payload)
        try:
            media_items = self.media_service.resolve_media_items(
                resolved_payload.media_ids,
                device_id=resolved_payload.device_id,
            )
        except MediaServiceError as exc:
            raise RetrievalServiceError(str(exc)) from exc
        search_payload = self._payload_with_media_context(resolved_payload, media_items)
        expansion = self.expansion_service.expand(search_payload)
        candidate_limit = max(resolved_payload.top_k * 20, 80)
        candidates = self.repository.list_knowledge_candidates(
            keywords=expansion.keywords,
            manufacturer=resolved_payload.manufacturer,
            product_series=resolved_payload.product_series,
            device_type=resolved_payload.device_type,
            document_type=resolved_payload.document_type,
            candidate_limit=candidate_limit,
        )
        scored_candidates = self._score_candidates(candidates, resolved_payload, expansion.keywords)
        vector_hits = []
        vector_diagnostics = {
            "vector_backend": "dashvector",
            "vector_available": False,
            "fallback_reason": None,
            "raw_vector_hits": 0,
            "verified_vector_hits": 0,
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_dimension": 0,
            "warnings": [],
        }
        vector_enabled = resolved_payload.enable_vector and resolved_payload.retrieval_mode != "keyword"
        if vector_enabled:
            vector_hits, vector_diagnostics = VectorIndexService(self.db).search(
                resolved_payload.normalized_question,
                top_k=resolved_payload.vector_top_k,
                filters={
                    "manufacturer": resolved_payload.manufacturer,
                    "product_series": resolved_payload.product_series,
                    "device_type": resolved_payload.device_type,
                    "document_type": resolved_payload.document_type,
                },
            )
        vector_available = bool(vector_diagnostics.get("vector_available") and vector_hits)
        vector_fallback_used = bool(resolved_payload.retrieval_mode in {"vector", "hybrid"} and not vector_available)
        actual_mode = resolved_payload.retrieval_mode
        if actual_mode in {"vector", "hybrid"} and vector_fallback_used:
            actual_mode = "keyword"
        merged_candidates = HybridRetrievalService.merge(
            keyword_candidates=scored_candidates,
            vector_hits=vector_hits,
            mode=actual_mode,
            keyword_weight=resolved_payload.hybrid_keyword_weight,
            vector_weight=resolved_payload.hybrid_vector_weight,
            min_score=resolved_payload.min_score,
            top_k=resolved_payload.top_k,
        )
        retrieved_chunks = [self._candidate_to_retrieved_chunk(candidate) for candidate in merged_candidates]
        references = self._build_references(retrieved_chunks)
        related_history = self._find_related_history(resolved_payload, expansion.keywords)
        kg_context = self._resolve_kg_context(resolved_payload, current_user)
        answer = self.answer_service.generate(
            payload=resolved_payload,
            retrieved_chunks=retrieved_chunks,
            keywords=expansion.keywords,
            kg_context=kg_context,
        )
        trace_id = self._new_trace_id()
        media_context = [self.media_service.media_context(item) for item in media_items]
        ocr_context = self.media_service.ocr_context(media_items) if resolved_payload.use_ocr_text else []
        media_notice = self._media_notice(
            media_context,
            use_ocr_text=resolved_payload.use_ocr_text,
            ocr_context=ocr_context,
        )
        answer_text = answer.answer
        if media_notice:
            answer_text = f"{answer_text}\n\n{media_notice}"
        response = RetrievalQueryResponse(
            trace_id=trace_id,
            question=resolved_payload.normalized_question,
            answer=answer_text,
            suggested_steps=answer.suggested_steps,
            safety_notes=answer.safety_notes,
            references=references,
            retrieved_chunks=retrieved_chunks,
            related_history=related_history,
            media_items=media_context,
            media_notice=media_notice,
            ocr_context=ocr_context,
            kg_context=kg_context,
            kg_nodes=kg_context.get("kg_nodes", []),
            kg_edges=kg_context.get("kg_edges", []),
            kg_evidence=kg_context.get("evidence", []),
            kg_paths=kg_context.get("graph_paths", []),
            confidence=answer.confidence,
            model_provider=MODEL_PROVIDER,
            model_name=MODEL_NAME,
            retrieval_mode=actual_mode,
            vector_enabled=vector_enabled,
            vector_available=vector_available,
            hybrid_used=actual_mode == "hybrid" and any(item.retrieval_source == "hybrid" for item in retrieved_chunks),
            vector_fallback_used=vector_fallback_used,
            fallback_used=vector_fallback_used,
            fallback_reason=vector_diagnostics.get("fallback_reason"),
            vector_backend=str(vector_diagnostics.get("vector_backend") or "unavailable"),
            embedding_provider=vector_diagnostics.get("embedding_provider"),
            embedding_model=vector_diagnostics.get("embedding_model"),
            retrieval_diagnostics={
                **vector_diagnostics,
                "requested_retrieval_mode": resolved_payload.retrieval_mode,
                "actual_retrieval_mode": actual_mode,
                "keyword_candidate_count": len(scored_candidates),
                "vector_hit_count": len(vector_hits),
                "merged_candidate_count": len(merged_candidates),
                "hybrid_keyword_weight": resolved_payload.hybrid_keyword_weight,
                "hybrid_vector_weight": resolved_payload.hybrid_vector_weight,
                "min_score": resolved_payload.min_score,
            },
            query_analysis=RetrievalQueryAnalysis(
                normalized_query=expansion.normalized_query,
                keywords=expansion.keywords,
                filters={
                    "manufacturer": resolved_payload.manufacturer,
                    "product_series": resolved_payload.product_series,
                    "device_type": resolved_payload.device_type,
                    "device_id": str(resolved_payload.device_id) if resolved_payload.device_id else None,
                    "document_type": resolved_payload.document_type,
                    "fault_type": resolved_payload.fault_type,
                    "alarm_code": resolved_payload.alarm_code,
                    "top_k": resolved_payload.top_k,
                    "media_ids": [str(media_id) for media_id in resolved_payload.media_ids],
                    "use_ocr_text": resolved_payload.use_ocr_text,
                    "enable_vector_search": resolved_payload.enable_vector_search,
                    "enable_kg_enhancement": resolved_payload.enable_kg_enhancement,
                    "retrieval_mode": resolved_payload.retrieval_mode,
                    "actual_retrieval_mode": actual_mode,
                    "enable_vector": resolved_payload.enable_vector,
                    "vector_top_k": resolved_payload.vector_top_k,
                },
            ),
        )
        self._apply_model_enhancement(response, resolved_payload, current_user)
        if response.media_notice and response.media_notice not in response.answer:
            response.answer = f"{response.answer}\n\n{response.media_notice}"
        self._save_qa_record(response, resolved_payload, current_user, media_items)
        return response

    def query_stream_events(self, payload: RetrievalQueryRequest, current_user: User):
        context = self._build_base_response(payload, current_user)
        response = context.response
        yield {
            "type": "retrieval",
            "response": response.model_dump(mode="json"),
        }

        if not context.payload.enable_model_enhancement:
            response.model_enhanced = False
            self._save_qa_record(response, context.payload, current_user, context.media_items)
            yield {
                "type": "delta",
                "content": response.answer,
            }
            yield {
                "type": "done",
                "response": response.model_dump(mode="json"),
            }
            return

        prompt = self.prompt_builder.build_retrieval_prompt(
            question=response.question,
            answer=response.answer,
            suggested_steps=response.suggested_steps,
            safety_notes=response.safety_notes,
            references=response.references,
            retrieved_chunks=response.retrieved_chunks,
            media_context=response.media_items,
            kg_context=response.kg_context,
        )
        content_parts: list[str] = []
        last_model_event: dict | None = None
        for event in ModelEnhancementService(self.db).stream_enhance(
            prompt=prompt,
            task_type="qa",
            requested_provider=context.payload.model_provider,
            allow_fallback=context.payload.allow_model_fallback,
            current_user=current_user,
        ):
            event_type = event.get("type")
            if event_type == "delta":
                chunk = str(event.get("content") or "")
                if not chunk:
                    continue
                content_parts.append(chunk)
                yield {
                    "type": "delta",
                    "content": chunk,
                    "model_call_trace_id": event.get("trace_id"),
                    "model_provider": event.get("provider"),
                    "model_name": event.get("model_name"),
                }
                continue
            last_model_event = event
            if event_type == "error":
                response.model_call_trace_id = event.get("trace_id")
                response.model_provider = event.get("provider") or response.model_provider
                response.model_name = event.get("model_name") or response.model_name
                response.fallback_used = False
                partial_content = "".join(content_parts).strip()
                if partial_content:
                    response.answer = partial_content
                    response.model_enhanced = True
                self._save_qa_record(response, context.payload, current_user, context.media_items)
                yield {
                    "type": "error",
                    "message": event.get("message") or "Model stream failed.",
                    "response": response.model_dump(mode="json"),
                }
                return

        final_content = "".join(content_parts).strip()
        if last_model_event and last_model_event.get("content"):
            final_content = str(last_model_event.get("content") or "").strip()
        if final_content:
            response.answer = final_content
            response.model_enhanced = True
            response.fallback_used = False
        if response.media_notice and response.media_notice not in response.answer:
            response.answer = f"{response.answer}\n\n{response.media_notice}"
        if last_model_event:
            response.model_call_trace_id = last_model_event.get("trace_id")
            response.model_provider = last_model_event.get("provider") or response.model_provider
            response.model_name = last_model_event.get("model_name") or response.model_name
        self._save_qa_record(response, context.payload, current_user, context.media_items)
        yield {
            "type": "done",
            "response": response.model_dump(mode="json"),
        }

    def _build_base_response(
        self,
        payload: RetrievalQueryRequest,
        current_user: User,
    ) -> RetrievalQueryContext:
        self._validate_request(payload)
        resolved_payload = self._resolve_device_context(payload)
        try:
            media_items = self.media_service.resolve_media_items(
                resolved_payload.media_ids,
                device_id=resolved_payload.device_id,
            )
        except MediaServiceError as exc:
            raise RetrievalServiceError(str(exc)) from exc
        search_payload = self._payload_with_media_context(resolved_payload, media_items)
        expansion = self.expansion_service.expand(search_payload)
        candidate_limit = max(resolved_payload.top_k * 20, 80)
        candidates = self.repository.list_knowledge_candidates(
            keywords=expansion.keywords,
            manufacturer=resolved_payload.manufacturer,
            product_series=resolved_payload.product_series,
            device_type=resolved_payload.device_type,
            document_type=resolved_payload.document_type,
            candidate_limit=candidate_limit,
        )
        scored_candidates = self._score_candidates(candidates, resolved_payload, expansion.keywords)
        vector_hits = []
        vector_diagnostics = {
            "vector_backend": "dashvector",
            "vector_available": False,
            "fallback_reason": None,
            "raw_vector_hits": 0,
            "verified_vector_hits": 0,
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_dimension": 0,
            "warnings": [],
        }
        vector_enabled = resolved_payload.enable_vector and resolved_payload.retrieval_mode != "keyword"
        if vector_enabled:
            vector_hits, vector_diagnostics = VectorIndexService(self.db).search(
                resolved_payload.normalized_question,
                top_k=resolved_payload.vector_top_k,
                filters={
                    "manufacturer": resolved_payload.manufacturer,
                    "product_series": resolved_payload.product_series,
                    "device_type": resolved_payload.device_type,
                    "document_type": resolved_payload.document_type,
                },
            )
        vector_available = bool(vector_diagnostics.get("vector_available") and vector_hits)
        vector_fallback_used = bool(resolved_payload.retrieval_mode in {"vector", "hybrid"} and not vector_available)
        actual_mode = resolved_payload.retrieval_mode
        if actual_mode in {"vector", "hybrid"} and vector_fallback_used:
            actual_mode = "keyword"
        merged_candidates = HybridRetrievalService.merge(
            keyword_candidates=scored_candidates,
            vector_hits=vector_hits,
            mode=actual_mode,
            keyword_weight=resolved_payload.hybrid_keyword_weight,
            vector_weight=resolved_payload.hybrid_vector_weight,
            min_score=resolved_payload.min_score,
            top_k=resolved_payload.top_k,
        )
        retrieved_chunks = [self._candidate_to_retrieved_chunk(candidate) for candidate in merged_candidates]
        references = self._build_references(retrieved_chunks)
        related_history = self._find_related_history(resolved_payload, expansion.keywords)
        kg_context = self._resolve_kg_context(resolved_payload, current_user)
        answer = self.answer_service.generate(
            payload=resolved_payload,
            retrieved_chunks=retrieved_chunks,
            keywords=expansion.keywords,
            kg_context=kg_context,
        )
        trace_id = self._new_trace_id()
        media_context = [self.media_service.media_context(item) for item in media_items]
        ocr_context = self.media_service.ocr_context(media_items) if resolved_payload.use_ocr_text else []
        media_notice = self._media_notice(
            media_context,
            use_ocr_text=resolved_payload.use_ocr_text,
            ocr_context=ocr_context,
        )
        answer_text = answer.answer
        if media_notice:
            answer_text = f"{answer_text}\n\n{media_notice}"
        response = RetrievalQueryResponse(
            trace_id=trace_id,
            question=resolved_payload.normalized_question,
            answer=answer_text,
            suggested_steps=answer.suggested_steps,
            safety_notes=answer.safety_notes,
            references=references,
            retrieved_chunks=retrieved_chunks,
            related_history=related_history,
            media_items=media_context,
            media_notice=media_notice,
            ocr_context=ocr_context,
            kg_context=kg_context,
            kg_nodes=kg_context.get("kg_nodes", []),
            kg_edges=kg_context.get("kg_edges", []),
            kg_evidence=kg_context.get("evidence", []),
            kg_paths=kg_context.get("graph_paths", []),
            confidence=answer.confidence,
            model_provider=MODEL_PROVIDER,
            model_name=MODEL_NAME,
            retrieval_mode=actual_mode,
            vector_enabled=vector_enabled,
            vector_available=vector_available,
            hybrid_used=actual_mode == "hybrid" and any(item.retrieval_source == "hybrid" for item in retrieved_chunks),
            vector_fallback_used=vector_fallback_used,
            fallback_used=vector_fallback_used,
            fallback_reason=vector_diagnostics.get("fallback_reason"),
            vector_backend=str(vector_diagnostics.get("vector_backend") or "unavailable"),
            embedding_provider=vector_diagnostics.get("embedding_provider"),
            embedding_model=vector_diagnostics.get("embedding_model"),
            retrieval_diagnostics={
                **vector_diagnostics,
                "requested_retrieval_mode": resolved_payload.retrieval_mode,
                "actual_retrieval_mode": actual_mode,
                "keyword_candidate_count": len(scored_candidates),
                "vector_hit_count": len(vector_hits),
                "merged_candidate_count": len(merged_candidates),
                "hybrid_keyword_weight": resolved_payload.hybrid_keyword_weight,
                "hybrid_vector_weight": resolved_payload.hybrid_vector_weight,
                "min_score": resolved_payload.min_score,
            },
            query_analysis=RetrievalQueryAnalysis(
                normalized_query=expansion.normalized_query,
                keywords=expansion.keywords,
                filters={
                    "manufacturer": resolved_payload.manufacturer,
                    "product_series": resolved_payload.product_series,
                    "device_type": resolved_payload.device_type,
                    "device_id": str(resolved_payload.device_id) if resolved_payload.device_id else None,
                    "document_type": resolved_payload.document_type,
                    "fault_type": resolved_payload.fault_type,
                    "alarm_code": resolved_payload.alarm_code,
                    "top_k": resolved_payload.top_k,
                    "media_ids": [str(media_id) for media_id in resolved_payload.media_ids],
                    "use_ocr_text": resolved_payload.use_ocr_text,
                    "enable_vector_search": resolved_payload.enable_vector_search,
                    "enable_kg_enhancement": resolved_payload.enable_kg_enhancement,
                    "retrieval_mode": resolved_payload.retrieval_mode,
                    "actual_retrieval_mode": actual_mode,
                    "enable_vector": resolved_payload.enable_vector,
                    "vector_top_k": resolved_payload.vector_top_k,
                },
            ),
        )
        return RetrievalQueryContext(
            response=response,
            payload=resolved_payload,
            media_items=media_items,
        )

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
            "items": [QARecordRead.model_validate(record).model_dump(mode="json") for record in records],
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
        if payload.vector_top_k < 1 or payload.vector_top_k > 20:
            raise RetrievalServiceError("vector_top_k must be between 1 and 20")
        if payload.retrieval_mode not in {"keyword", "vector", "hybrid"}:
            raise RetrievalServiceError("retrieval_mode must be keyword, vector, or hybrid")
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

    def _resolve_device_context(self, payload: RetrievalQueryRequest) -> RetrievalQueryRequest:
        if not payload.device_id:
            return payload
        device = self.repository.get_device(payload.device_id)
        if not device:
            raise RetrievalServiceError("Device not found")
        update_data = payload.model_dump()
        update_data["manufacturer"] = payload.manufacturer or device.manufacturer
        update_data["product_series"] = payload.product_series or device.product_series
        update_data["device_type"] = payload.device_type or device.device_type
        return RetrievalQueryRequest(**update_data)

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
        data["question"] = "\n".join([payload.normalized_question, *media_texts])
        return RetrievalQueryRequest(**data)

    def _score_candidates(
        self,
        candidates: list[tuple[KnowledgeChunk, KnowledgeDocument]],
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> list[HybridScoredCandidate]:
        scored: list[HybridScoredCandidate] = []
        for chunk, document in candidates:
            score = self._score_candidate(chunk, document, payload, keywords)
            if score <= 0:
                continue
            scored.append(
                HybridScoredCandidate(
                    chunk=chunk,
                    document=document,
                    score=round(score, 2),
                    keyword_score=round(score, 2),
                    retrieval_source="keyword",
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    def _score_candidate(
        self,
        chunk: KnowledgeChunk,
        document: KnowledgeDocument,
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> float:
        score = 0.0
        content = chunk.content or ""
        section_title = chunk.section_title or ""
        document_title = document.title or ""
        document_summary = document.summary or ""
        document_source = document.source or ""

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            score += min(self._hit_count(content, keyword), 4) * 2.0
            score += min(self._hit_count(section_title, keyword), 2) * 5.0
            score += min(self._hit_count(document_title, keyword), 2) * 6.0
            score += min(self._hit_count(document_summary, keyword), 2) * 3.0
            score += min(self._hit_count(document_source, keyword), 1) * 1.0

        if payload.alarm_code:
            alarm = payload.alarm_code.lower()
            joined_text = " ".join([content, section_title, document_title, document_summary]).lower()
            if alarm and alarm in joined_text:
                score += 12.0
        if payload.manufacturer and payload.manufacturer == document.manufacturer:
            score += 3.0
        if payload.product_series and payload.product_series == document.product_series:
            score += 3.0
        if payload.document_type and payload.document_type == document.document_type:
            score += 2.0
        if document.created_at:
            score += 0.2
        if chunk.char_count and chunk.char_count < 40:
            score -= 2.0
        return score

    @staticmethod
    def _hit_count(text: str, keyword: str) -> int:
        if not text or not keyword:
            return 0
        return len(re.findall(re.escape(keyword.lower()), text.lower()))

    @staticmethod
    def _candidate_to_retrieved_chunk(candidate: HybridScoredCandidate) -> RetrievedChunk:
        chunk = candidate.chunk
        document = candidate.document
        return RetrievedChunk(
            chunk_id=chunk.id,
            document_id=document.id,
            document_title=document.title,
            chunk_index=chunk.chunk_index,
            section_title=chunk.section_title,
            page_number=chunk.page_number,
            content=chunk.content,
            score=candidate.score,
            manufacturer=document.manufacturer,
            product_series=document.product_series,
            device_type=document.device_type,
            document_type=document.document_type,
            source=document.source,
            created_at=chunk.created_at,
            keyword_score=candidate.keyword_score,
            vector_score=candidate.vector_score,
            hybrid_score=candidate.hybrid_score,
            retrieval_source=candidate.retrieval_source,
            vector_backend=candidate.vector_backend,
        )

    def _build_references(self, chunks: list[RetrievedChunk]) -> list[RetrievalReference]:
        references: list[RetrievalReference] = []
        for chunk in chunks:
            references.append(
                RetrievalReference(
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    quote=self._quote(chunk.content),
                    manufacturer=chunk.manufacturer,
                    product_series=chunk.product_series,
                    device_type=chunk.device_type,
                    document_type=chunk.document_type,
                    source=chunk.source,
                    score=chunk.score,
                )
            )
        return references

    @staticmethod
    def _quote(content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        return compact[:180]

    def _find_related_history(
        self,
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> list[RelatedHistoryItem]:
        if not payload.include_history or not payload.device_id:
            return []
        records = self.repository.list_history_candidates(
            device_id=payload.device_id,
            keywords=keywords,
            fault_type=payload.fault_type,
            alarm_code=payload.alarm_code,
            candidate_limit=20,
        )
        if not records:
            records = self.repository.list_recent_history_by_device(
                device_id=payload.device_id,
                candidate_limit=20,
            )
        scored = sorted(
            records,
            key=lambda record: self._score_history(record, payload, keywords),
            reverse=True,
        )
        return [self._history_payload(record) for record in scored[:3]]

    def _score_history(
        self,
        record: DeviceMaintenanceRecord,
        payload: RetrievalQueryRequest,
        keywords: list[str],
    ) -> float:
        score = 1.0
        if payload.fault_type and payload.fault_type == record.fault_type:
            score += 8.0
        if payload.alarm_code and record.alarm_code and payload.alarm_code.lower() == record.alarm_code.lower():
            score += 8.0
        text = " ".join(
            [
                record.fault_description or "",
                record.root_cause or "",
                record.repair_action or "",
                record.verification_result or "",
            ]
        )
        for keyword in keywords[:40]:
            score += min(self._hit_count(text, keyword), 3)
        return score

    @staticmethod
    def _history_payload(record: DeviceMaintenanceRecord) -> RelatedHistoryItem:
        return RelatedHistoryItem(
            record_id=record.id,
            device_id=record.device_id,
            fault_type=record.fault_type,
            alarm_code=record.alarm_code,
            fault_description=record.fault_description,
            root_cause=record.root_cause,
            repair_action=record.repair_action,
            verification_result=record.verification_result,
            is_recurrent=record.is_recurrent,
            completed_at=record.completed_at,
        )

    def _save_qa_record(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
        media_items: list,
    ) -> None:
        stored_history = [item.model_dump(mode="json") for item in response.related_history]
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
                    **self._kg_context_summary(response.kg_context),
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
            references=[item.model_dump(mode="json") for item in response.references],
            retrieved_chunks=[item.model_dump(mode="json") for item in response.retrieved_chunks],
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
            raise RetrievalServiceError(f"QA record write failed: {exc}") from exc

    def _apply_model_enhancement(
        self,
        response: RetrievalQueryResponse,
        payload: RetrievalQueryRequest,
        current_user: User,
    ) -> None:
        if not payload.enable_model_enhancement:
            return
        prompt = self.prompt_builder.build_retrieval_prompt(
            question=response.question,
            answer=response.answer,
            suggested_steps=response.suggested_steps,
            safety_notes=response.safety_notes,
            references=response.references,
            retrieved_chunks=response.retrieved_chunks,
            media_context=response.media_items,
            kg_context=response.kg_context,
        )
        enhancement = ModelEnhancementService(self.db).enhance(
            prompt=prompt,
            task_type="qa",
            requested_provider=payload.model_provider,
            allow_fallback=payload.allow_model_fallback,
            current_user=current_user,
            default_provider=MODEL_PROVIDER,
            default_model_name=MODEL_NAME,
        )
        if enhancement.content:
            response.answer = enhancement.content
        ModelEnhancementService.apply_metadata(response, enhancement)

    def _resolve_kg_context(self, payload: RetrievalQueryRequest, current_user: User) -> dict:
        if not payload.enable_kg_enhancement:
            return {}
        return KnowledgeGraphService(self.db).business_context(
            current_user=current_user,
            device_id=payload.device_id,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            fault_type=payload.fault_type,
            alarm_code=payload.alarm_code,
            question=payload.normalized_question,
        )

    @staticmethod
    def _kg_context_summary(kg_context: dict) -> dict:
        summary = kg_context.get("summary") or {}
        return {
            "summary": summary,
            "matched_nodes": [
                {
                    "id": item.get("id"),
                    "node_type": item.get("node_type"),
                    "display_name": item.get("display_name"),
                }
                for item in (kg_context.get("matched_nodes") or [])[:8]
            ],
            "related_causes": kg_context.get("related_causes", [])[:5],
            "inspection_items": kg_context.get("inspection_items", [])[:5],
            "recommended_actions": kg_context.get("recommended_actions", [])[:5],
            "safety_risks": kg_context.get("safety_risks", [])[:5],
            "evidence_count": len(kg_context.get("evidence") or []),
        }

    @staticmethod
    def _new_trace_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"qa_{timestamp}_{uuid4().hex[:10]}"

    @staticmethod
    def _media_notice(
        media_items: list,
        *,
        use_ocr_text: bool = False,
        ocr_context: list[dict] | None = None,
    ) -> str | None:
        if not media_items:
            return None
        if use_ocr_text and ocr_context:
            return "OCR text from selected images was included as machine-recognized context for reference only."
        if use_ocr_text:
            return "OCR text was requested, but selected images do not have processed OCR text yet."
        return "Images are attached as human-review evidence; OCR text was not included in this answer."

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise RetrievalServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise RetrievalServiceError("page_size must be between 1 and 100")
