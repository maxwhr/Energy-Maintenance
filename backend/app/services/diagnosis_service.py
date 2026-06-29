from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Device, DiagnosisRecord, KnowledgeChunk, KnowledgeDocument, UploadedMedia, User
from app.repositories.diagnosis_repository import DiagnosisRepository
from app.repositories.retrieval_repository import RetrievalRepository
from app.schemas.diagnosis import (
    ALLOWED_DIAGNOSIS_DEVICE_TYPES,
    ALLOWED_DIAGNOSIS_FAULT_TYPES,
    ALLOWED_DIAGNOSIS_MANUFACTURERS,
    ALLOWED_DIAGNOSIS_PRODUCT_SERIES,
    DiagnosisAnalyzeRequest,
    DiagnosisAnalyzeResponse,
    DiagnosisRecordItem,
    DiagnosisReference,
)
from app.schemas.retrieval import RetrievalQueryRequest
from app.services.diagnosis_rule_engine import MODEL_NAME, MODEL_PROVIDER, DiagnosisRuleEngine
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.media_service import MediaService, MediaServiceError
from app.services.model_enhancement_service import ModelEnhancementService
from app.services.model_prompt_builder import ModelPromptBuilder
from app.services.query_expansion_service import QueryExpansionService
from app.services.recurrence_service import RecurrenceService


class DiagnosisServiceError(ValueError):
    pass


@dataclass
class ScoredDiagnosisCandidate:
    chunk: KnowledgeChunk
    document: KnowledgeDocument
    score: float


class DiagnosisService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DiagnosisRepository(db)
        self.retrieval_repository = RetrievalRepository(db)
        self.rule_engine = DiagnosisRuleEngine()
        self.query_expansion = QueryExpansionService()
        self.recurrence_service = RecurrenceService()
        self.prompt_builder = ModelPromptBuilder()
        self.media_service = MediaService(db)

    def analyze(self, payload: DiagnosisAnalyzeRequest, current_user: User) -> DiagnosisAnalyzeResponse:
        self._validate_request(payload)
        device = self._resolve_device(payload.device_id)
        resolved_payload = self._resolve_payload(payload, device)
        try:
            media_items = self.media_service.resolve_media_items(
                resolved_payload.media_ids,
                device_id=resolved_payload.device_id,
            )
        except MediaServiceError as exc:
            raise DiagnosisServiceError(str(exc)) from exc
        media_texts = self.media_service.media_context_texts(
            media_items,
            include_ocr_text=resolved_payload.use_ocr_text,
        )
        rule_result = self.rule_engine.analyze(
            fault_type=resolved_payload.fault_type,
            fault_description=resolved_payload.fault_description,
            observed_symptoms=resolved_payload.observed_symptoms,
            media_texts=media_texts,
        )
        retrieval_payload = self._retrieval_payload(resolved_payload, rule_result.fault_type, media_texts)
        expansion = self.query_expansion.expand(retrieval_payload)
        references = self._find_references(retrieval_payload, expansion.keywords, top_k=5)
        history_result = self._find_recurrence(resolved_payload, rule_result.fault_type, expansion.keywords)
        kg_context = self._resolve_kg_context(resolved_payload, rule_result.fault_type, current_user)
        confidence = self._confidence(
            fault_type=rule_result.fault_type,
            references=references,
            is_recurrent=history_result.is_recurrent,
        )
        trace_id = self._new_trace_id()
        media_context = [self.media_service.media_context(item) for item in media_items]
        ocr_context = self.media_service.ocr_context(media_items) if resolved_payload.use_ocr_text else []
        media_notice = self._media_notice(
            media_context,
            use_ocr_text=resolved_payload.use_ocr_text,
            ocr_context=ocr_context,
        )
        diagnosis_summary = rule_result.diagnosis_summary
        if media_notice:
            diagnosis_summary = f"{diagnosis_summary}\n\n{media_notice}"
        response = DiagnosisAnalyzeResponse(
            trace_id=trace_id,
            device_id=resolved_payload.device_id,
            fault_type=rule_result.fault_type,
            alarm_code=resolved_payload.alarm_code,
            diagnosis_summary=diagnosis_summary,
            possible_causes=rule_result.possible_causes,
            inspection_steps=rule_result.inspection_steps,
            recommended_actions=rule_result.recommended_actions,
            safety_notes=rule_result.safety_notes,
            references=references,
            related_history=history_result.related_history,
            media_ids=resolved_payload.media_ids,
            media_items=media_context,
            media_notice=media_notice,
            ocr_context=ocr_context,
            kg_context=kg_context,
            kg_related_causes=kg_context.get("related_causes", []),
            kg_inspection_items=kg_context.get("inspection_items", []),
            kg_recommended_actions=kg_context.get("recommended_actions", []),
            kg_safety_risks=kg_context.get("safety_risks", []),
            kg_evidence=kg_context.get("evidence", []),
            is_recurrent=history_result.is_recurrent,
            recurrent_reference_record_id=history_result.recurrent_reference_record_id,
            confidence=confidence,
            model_provider=MODEL_PROVIDER,
            model_name=MODEL_NAME,
        )
        self._apply_model_enhancement(response, resolved_payload, current_user)
        if response.media_notice and response.media_notice not in response.diagnosis_summary:
            response.diagnosis_summary = f"{response.diagnosis_summary}\n\n{response.media_notice}"

        record = DiagnosisRecord(
            trace_id=trace_id,
            device_id=resolved_payload.device_id,
            manufacturer=resolved_payload.manufacturer,
            product_series=resolved_payload.product_series,
            device_type=resolved_payload.device_type or "pv_inverter",
            device_name=device.device_name if device else None,
            model=resolved_payload.model,
            fault_type=response.fault_type,
            alarm_code=resolved_payload.alarm_code,
            alarm_info="\n".join(resolved_payload.observed_symptoms) if resolved_payload.observed_symptoms else None,
            fault_description=resolved_payload.fault_description,
            possible_causes=response.possible_causes,
            inspection_steps=response.inspection_steps,
            safety_notes=response.safety_notes,
            recommended_actions=response.recommended_actions,
            references=[item.model_dump(mode="json") for item in response.references],
            related_history=[
                *[item.model_dump(mode="json") for item in response.related_history],
                *[{"record_type": "ocr_context", **item} for item in response.ocr_context],
                *([{"record_type": "kg_context_summary", **self._kg_context_summary(response.kg_context)}] if response.kg_context else []),
            ],
            media_ids=[str(media_id) for media_id in resolved_payload.media_ids],
            model_provider=response.model_provider,
            model_name=response.model_name,
            confidence=response.confidence,
            created_by=current_user.id,
        )
        try:
            saved = self.repository.create_record(record)
            self.repository.link_media_to_record(media_items, saved.id)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DiagnosisServiceError(f"Diagnosis record write failed: {exc}") from exc

        response.trace_id = saved.trace_id
        response.device_id = saved.device_id
        response.alarm_code = saved.alarm_code
        return response

    def list_records(
        self,
        *,
        device_id: UUID | None = None,
        manufacturer: str | None = None,
        product_series: str | None = None,
        fault_type: str | None = None,
        alarm_code: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        records, total = self.repository.list_records(
            device_id=device_id,
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            alarm_code=alarm_code,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._record_item(record).model_dump(mode="json") for record in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_record_detail(self, trace_id: str) -> dict | None:
        record = self.repository.get_by_trace_id(trace_id)
        if not record:
            return None
        return self._record_item(record).model_dump(mode="json")

    @staticmethod
    def _validate_request(payload: DiagnosisAnalyzeRequest) -> None:
        if not payload.fault_description or not payload.fault_description.strip():
            raise DiagnosisServiceError("fault_description must not be empty")
        if payload.manufacturer and payload.manufacturer not in ALLOWED_DIAGNOSIS_MANUFACTURERS:
            raise DiagnosisServiceError("manufacturer must be huawei or sungrow")
        if payload.product_series and payload.product_series not in ALLOWED_DIAGNOSIS_PRODUCT_SERIES:
            raise DiagnosisServiceError("unsupported product_series")
        if payload.device_type not in ALLOWED_DIAGNOSIS_DEVICE_TYPES:
            raise DiagnosisServiceError("device_type must be pv_inverter")
        if payload.fault_type and payload.fault_type not in ALLOWED_DIAGNOSIS_FAULT_TYPES:
            raise DiagnosisServiceError("unsupported fault_type")
        if len(payload.media_ids) > 10:
            raise DiagnosisServiceError("media_ids supports at most 10 media items")

    def _resolve_device(self, device_id: UUID | None) -> Device | None:
        if not device_id:
            return None
        device = self.repository.get_device(device_id)
        if not device:
            raise DiagnosisServiceError("Device not found")
        if device.device_type != "pv_inverter":
            raise DiagnosisServiceError("device_type must be pv_inverter")
        return device

    @staticmethod
    def _resolve_payload(payload: DiagnosisAnalyzeRequest, device: Device | None) -> DiagnosisAnalyzeRequest:
        data = payload.model_dump()
        if device:
            data["manufacturer"] = device.manufacturer
            data["product_series"] = device.product_series
            data["model"] = device.model
            data["device_type"] = device.device_type
        return DiagnosisAnalyzeRequest(**data)

    @staticmethod
    def _retrieval_payload(
        payload: DiagnosisAnalyzeRequest,
        normalized_fault_type: str,
        media_texts: list[str],
    ) -> RetrievalQueryRequest:
        question_parts = [
            payload.fault_description,
            *payload.observed_symptoms,
            *media_texts,
        ]
        return RetrievalQueryRequest(
            question="\n".join(part for part in question_parts if part),
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            device_id=payload.device_id,
            fault_type=normalized_fault_type,
            alarm_code=payload.alarm_code,
            top_k=5,
            include_history=payload.include_history,
        )

    def _find_references(
        self,
        payload: RetrievalQueryRequest,
        keywords: list[str],
        *,
        top_k: int,
    ) -> list[DiagnosisReference]:
        candidates = self.retrieval_repository.list_knowledge_candidates(
            keywords=keywords,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            document_type=None,
            candidate_limit=max(top_k * 20, 80),
        )
        scored: list[ScoredDiagnosisCandidate] = []
        for chunk, document in candidates:
            score = self._score_candidate(chunk, document, payload, keywords)
            if score <= 0:
                continue
            scored.append(ScoredDiagnosisCandidate(chunk=chunk, document=document, score=round(score, 2)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return [self._reference_from_candidate(candidate) for candidate in scored[:top_k]]

    def _find_recurrence(
        self,
        payload: DiagnosisAnalyzeRequest,
        fault_type: str,
        keywords: list[str],
    ):
        if not payload.include_history or not payload.device_id:
            return self.recurrence_service.evaluate(
                device_id=None,
                fault_type=fault_type,
                alarm_code=payload.alarm_code,
                fault_description=payload.fault_description,
                keywords=keywords,
                history_records=[],
            )
        history_records = self.repository.list_recent_history_by_device(
            device_id=payload.device_id,
            candidate_limit=30,
        )
        return self.recurrence_service.evaluate(
            device_id=payload.device_id,
            fault_type=fault_type,
            alarm_code=payload.alarm_code,
            fault_description=payload.fault_description,
            keywords=keywords,
            history_records=history_records,
        )

    def _apply_model_enhancement(
        self,
        response: DiagnosisAnalyzeResponse,
        payload: DiagnosisAnalyzeRequest,
        current_user: User,
    ) -> None:
        if not payload.enable_model_enhancement:
            return
        prompt = self.prompt_builder.build_diagnosis_prompt(
            request_summary={
                "manufacturer": payload.manufacturer,
                "product_series": payload.product_series,
                "model": payload.model,
                "device_type": payload.device_type,
                "fault_type": payload.fault_type,
                "alarm_code": payload.alarm_code,
                "fault_description": payload.fault_description,
                "observed_symptoms": payload.observed_symptoms,
            },
            diagnosis_summary=response.diagnosis_summary,
            possible_causes=response.possible_causes,
            inspection_steps=response.inspection_steps,
            recommended_actions=response.recommended_actions,
            safety_notes=response.safety_notes,
            references=response.references,
            related_history=response.related_history,
            media_context=response.media_items,
            kg_context=response.kg_context,
        )
        enhancement = ModelEnhancementService(self.db).enhance(
            prompt=prompt,
            task_type="diagnosis",
            requested_provider=payload.model_provider,
            allow_fallback=payload.allow_model_fallback,
            current_user=current_user,
            default_provider=MODEL_PROVIDER,
            default_model_name=MODEL_NAME,
        )
        if enhancement.content:
            response.diagnosis_summary = enhancement.content
        ModelEnhancementService.apply_metadata(response, enhancement)

    def _resolve_kg_context(
        self,
        payload: DiagnosisAnalyzeRequest,
        normalized_fault_type: str,
        current_user: User,
    ) -> dict:
        if not payload.enable_kg_enhancement:
            return {}
        question = "\n".join(
            part
            for part in [
                payload.fault_description,
                *payload.observed_symptoms,
            ]
            if part
        )
        return KnowledgeGraphService(self.db).business_context(
            current_user=current_user,
            device_id=payload.device_id,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            fault_type=normalized_fault_type,
            alarm_code=payload.alarm_code,
            question=question,
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
        joined = " ".join([content, section_title, document_title, document_summary])

        for keyword in keywords:
            if len(keyword) < 2:
                continue
            score += min(self._hit_count(content, keyword), 4) * 2.0
            score += min(self._hit_count(section_title, keyword), 2) * 5.0
            score += min(self._hit_count(document_title, keyword), 2) * 5.0
            score += min(self._hit_count(document_summary, keyword), 2) * 2.0

        if payload.fault_type and payload.fault_type in joined:
            score += 4.0
        if payload.alarm_code and payload.alarm_code.lower() in joined.lower():
            score += 10.0
        if payload.manufacturer and payload.manufacturer == document.manufacturer:
            score += 2.0
        if payload.product_series and payload.product_series == document.product_series:
            score += 2.0
        if document.document_type in {"alarm_code", "fault_case", "manual", "sop"}:
            score += 1.0
        if chunk.char_count and chunk.char_count < 40:
            score -= 2.0
        return score

    @staticmethod
    def _hit_count(text: str, keyword: str) -> int:
        if not text or not keyword:
            return 0
        return len(re.findall(re.escape(keyword.lower()), text.lower()))

    @staticmethod
    def _reference_from_candidate(candidate: ScoredDiagnosisCandidate) -> DiagnosisReference:
        chunk = candidate.chunk
        document = candidate.document
        return DiagnosisReference(
            document_id=document.id,
            document_title=document.title,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            quote=DiagnosisService._quote(chunk.content),
            manufacturer=document.manufacturer,
            product_series=document.product_series,
            device_type=document.device_type,
            document_type=document.document_type,
            source=document.source,
            score=candidate.score,
        )

    @staticmethod
    def _quote(content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        return compact[:180]

    @staticmethod
    def _confidence(
        *,
        fault_type: str,
        references: list[DiagnosisReference],
        is_recurrent: bool,
    ) -> float:
        confidence = 0.42
        if fault_type != "unknown":
            confidence += 0.12
        if references:
            confidence += min(len(references), 5) * 0.04
        if is_recurrent:
            confidence += 0.08
        return round(min(confidence, 0.85), 2)

    @staticmethod
    def _new_trace_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"diag_{timestamp}_{uuid4().hex[:10]}"

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise DiagnosisServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise DiagnosisServiceError("page_size must be between 1 and 100")

    def _record_item(self, record: DiagnosisRecord) -> DiagnosisRecordItem:
        related_history = record.related_history or []
        kg_summary = next(
            (item for item in related_history if isinstance(item, dict) and item.get("record_type") == "kg_context_summary"),
            {},
        )
        ocr_context = [
            item
            for item in related_history
            if isinstance(item, dict) and item.get("record_type") == "ocr_context"
        ]
        recurrent_reference_record_id = None
        is_recurrent = False
        if related_history:
            for item in related_history:
                if isinstance(item, dict) and item.get("is_recurrent"):
                    is_recurrent = True
                    recurrent_reference_record_id = item.get("record_id")
                    break
        summary = DiagnosisService._summary_from_record(record)
        media_items = []
        try:
            resolved_media = self.media_service.resolve_media_items(
                [UUID(str(item)) for item in (record.media_ids or [])],
                device_id=record.device_id,
            )
            media_items = [self.media_service.media_context(item) for item in resolved_media]
        except (ValueError, MediaServiceError):
            media_items = []
        return DiagnosisRecordItem(
            id=record.id,
            trace_id=record.trace_id,
            device_id=record.device_id,
            device_name=record.device_name,
            manufacturer=record.manufacturer,
            product_series=record.product_series,
            model=record.model,
            device_type=record.device_type,
            fault_type=record.fault_type,
            alarm_code=record.alarm_code,
            fault_description=record.fault_description,
            diagnosis_summary=summary,
            possible_causes=record.possible_causes or [],
            inspection_steps=record.inspection_steps or [],
            recommended_actions=record.recommended_actions or [],
            safety_notes=record.safety_notes or [],
            references=record.references or [],
            related_history=related_history,
            media_ids=[str(item) for item in (record.media_ids or [])],
            media_items=media_items,
            media_notice=self._media_notice(media_items),
            ocr_context=ocr_context,
            kg_context=kg_summary,
            kg_related_causes=kg_summary.get("related_causes", []) if isinstance(kg_summary, dict) else [],
            kg_inspection_items=kg_summary.get("inspection_items", []) if isinstance(kg_summary, dict) else [],
            kg_recommended_actions=kg_summary.get("recommended_actions", []) if isinstance(kg_summary, dict) else [],
            kg_safety_risks=kg_summary.get("safety_risks", []) if isinstance(kg_summary, dict) else [],
            kg_evidence=[],
            is_recurrent=is_recurrent,
            recurrent_reference_record_id=recurrent_reference_record_id,
            confidence=record.confidence,
            model_provider=record.model_provider,
            model_name=record.model_name,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _summary_from_record(record: DiagnosisRecord) -> str:
        fault_type = record.fault_type or "unknown"
        first_cause = (record.possible_causes or ["需结合现场信息继续排查"])[0]
        return f"{fault_type} 初步诊断：{first_cause}"

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
        return "Images are attached as human-review evidence; OCR text was not included in this diagnosis."
