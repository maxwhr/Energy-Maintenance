from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Device, DiagnosisRecord, KnowledgeChunk, KnowledgeDocument, SOPTemplate, User
from app.repositories.sop_repository import SOPRepository
from app.schemas.sop import (
    ALLOWED_SOP_DEVICE_TYPES,
    ALLOWED_SOP_FAULT_TYPES,
    ALLOWED_SOP_MAINTENANCE_LEVELS,
    ALLOWED_SOP_MANUFACTURERS,
    ALLOWED_SOP_PRODUCT_SERIES,
    ALLOWED_SOP_TEMPLATE_STATUSES,
    SOPGenerateRequest,
    SOPGenerateResponse,
    SOPReference,
    SOPTemplateCreate,
    SOPTemplateRead,
    SOPTemplateUpdate,
)
from app.services.model_enhancement_service import ModelEnhancementService
from app.services.model_prompt_builder import ModelPromptBuilder
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.media_service import MediaService, MediaServiceError
from app.services.sop_rule_engine import SOP_RULE_ENGINE_NAME, SOPRuleEngine


class SOPServiceError(ValueError):
    pass


class SOPService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SOPRepository(db)
        self.rule_engine = SOPRuleEngine()
        self.prompt_builder = ModelPromptBuilder()
        self.media_service = MediaService(db)

    def list_templates(
        self,
        *,
        manufacturer: str | None = None,
        product_series: str | None = None,
        device_type: str | None = "pv_inverter",
        fault_type: str | None = None,
        maintenance_level: str | None = None,
        status: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        self._validate_page(page, page_size)
        self._validate_scope(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            fault_type=fault_type,
            maintenance_level=maintenance_level,
            status=status,
        )
        templates, total = self.repository.list_templates(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            fault_type=self.rule_engine.normalize_fault_type(fault_type) if fault_type else None,
            maintenance_level=maintenance_level,
            status=status,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self._template_payload(template) for template in templates],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_template(self, template_id: UUID) -> dict | None:
        template = self.repository.get_template(template_id)
        if not template:
            return None
        return self._template_payload(template)

    def create_template(self, payload: SOPTemplateCreate, current_user: User) -> dict:
        normalized_fault_type = self.rule_engine.normalize_fault_type(payload.fault_type)
        self._validate_scope(
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            fault_type=normalized_fault_type,
            maintenance_level=payload.maintenance_level,
            status=payload.status,
        )
        template = SOPTemplate(
            title=payload.title,
            manufacturer=payload.manufacturer,
            product_series=payload.product_series,
            device_type=payload.device_type,
            fault_type=normalized_fault_type,
            maintenance_level=payload.maintenance_level,
            steps=payload.steps,
            safety_requirements=payload.safety_requirements,
            tools_required=payload.tools_required,
            materials_required=payload.materials_required,
            compliance_notes=payload.compliance_notes,
            status=payload.status,
            version=payload.version,
            created_by=current_user.id,
            updated_by=current_user.id,
            metadata_json=payload.metadata_json,
        )
        try:
            saved = self.repository.create_template(template)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise SOPServiceError(f"SOP template write failed: {exc}") from exc
        return self._template_payload(saved)

    def update_template(self, template_id: UUID, payload: SOPTemplateUpdate, current_user: User) -> dict:
        template = self.repository.get_template(template_id)
        if not template:
            raise SOPServiceError("SOP template not found")
        data = payload.model_dump(exclude_unset=True)
        if "fault_type" in data and data["fault_type"]:
            data["fault_type"] = self.rule_engine.normalize_fault_type(data["fault_type"])
        if {
            "manufacturer",
            "product_series",
            "device_type",
            "fault_type",
            "maintenance_level",
            "status",
        }.intersection(data):
            self._validate_scope(
                manufacturer=data.get("manufacturer") or template.manufacturer,
                product_series=data.get("product_series") or template.product_series,
                device_type=data.get("device_type") or template.device_type,
                fault_type=data.get("fault_type") or template.fault_type,
                maintenance_level=data.get("maintenance_level") or template.maintenance_level,
                status=data.get("status") or template.status,
            )
        for field, value in data.items():
            setattr(template, field, value)
        template.updated_by = current_user.id
        try:
            saved = self.repository.update_template(template)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise SOPServiceError(f"SOP template update failed: {exc}") from exc
        return self._template_payload(saved)

    def archive_template(self, template_id: UUID, current_user: User) -> dict:
        template = self.repository.get_template(template_id)
        if not template:
            raise SOPServiceError("SOP template not found")
        template.status = "archived"
        template.updated_by = current_user.id
        try:
            saved = self.repository.update_template(template)
            self.db.commit()
            self.db.refresh(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise SOPServiceError(f"SOP template archive failed: {exc}") from exc
        return self._template_payload(saved)

    def generate(self, payload: SOPGenerateRequest, current_user: User) -> SOPGenerateResponse:
        resolved = self._resolve_generation_context(payload)
        template = self.repository.find_matching_template(
            manufacturer=resolved["manufacturer"],
            product_series=resolved["product_series"],
            device_type=resolved["device_type"],
            fault_type=resolved["fault_type"],
            maintenance_level=resolved["maintenance_level"],
        )
        references = self._resolve_references(
            diagnosis=resolved["diagnosis"],
            manufacturer=resolved["manufacturer"],
            product_series=resolved["product_series"],
            device_type=resolved["device_type"],
            fault_type=resolved["fault_type"],
            alarm_code=resolved["alarm_code"],
            include_references=payload.include_references,
        )
        media_context = self._diagnosis_media_context(resolved["diagnosis"])
        media_notice = self._media_notice(media_context)
        kg_context = self._resolve_kg_context(payload, resolved, current_user)

        if template:
            confidence = self._confidence(source="template", references=references)
            response = SOPGenerateResponse(
                source="template",
                template_id=template.id,
                title=template.title,
                manufacturer=resolved["manufacturer"] or template.manufacturer,
                product_series=resolved["product_series"] or template.product_series,
                model=resolved["model"],
                device_type=template.device_type,
                fault_type=template.fault_type or resolved["fault_type"],
                alarm_code=resolved["alarm_code"],
                maintenance_level=template.maintenance_level,
                steps=template.steps or [],
                safety_requirements=template.safety_requirements or [],
                tools_required=template.tools_required or [],
                materials_required=template.materials_required or [],
                compliance_notes=template.compliance_notes,
                references=references,
                media_items=media_context,
                media_notice=media_notice,
                kg_context=kg_context,
                kg_tools=kg_context.get("tools", []),
                kg_parts=kg_context.get("parts", []),
                kg_safety_risks=kg_context.get("safety_risks", []),
                kg_steps=[
                    *kg_context.get("inspection_items", [])[:5],
                    *kg_context.get("recommended_actions", [])[:5],
                ],
                kg_evidence=kg_context.get("evidence", []),
                confidence=confidence,
                model_provider="rule_based",
                model_name=SOP_RULE_ENGINE_NAME,
            )
            self._apply_model_enhancement(response, payload, current_user)
            return response

        diagnosis = resolved["diagnosis"]
        rule_result = self.rule_engine.generate(
            manufacturer=resolved["manufacturer"],
            product_series=resolved["product_series"],
            model=resolved["model"],
            fault_type=resolved["fault_type"],
            alarm_code=resolved["alarm_code"],
            maintenance_level=resolved["maintenance_level"],
            diagnosis_steps=diagnosis.inspection_steps if diagnosis else None,
            diagnosis_actions=diagnosis.recommended_actions if diagnosis else None,
        )
        confidence = self._confidence(source="rule_based", references=references, base=rule_result.confidence)
        response = SOPGenerateResponse(
            source="rule_based",
            template_id=None,
            title=rule_result.title,
            manufacturer=resolved["manufacturer"],
            product_series=resolved["product_series"],
            model=resolved["model"],
            device_type=resolved["device_type"],
            fault_type=rule_result.fault_type,
            alarm_code=resolved["alarm_code"],
            maintenance_level=rule_result.maintenance_level,
            steps=rule_result.steps,
            safety_requirements=rule_result.safety_requirements,
            tools_required=rule_result.tools_required,
            materials_required=rule_result.materials_required,
            compliance_notes=rule_result.compliance_notes,
            references=references,
            media_items=media_context,
            media_notice=media_notice,
            kg_context=kg_context,
            kg_tools=kg_context.get("tools", []),
            kg_parts=kg_context.get("parts", []),
            kg_safety_risks=kg_context.get("safety_risks", []),
            kg_steps=[
                *kg_context.get("inspection_items", [])[:5],
                *kg_context.get("recommended_actions", [])[:5],
            ],
            kg_evidence=kg_context.get("evidence", []),
            confidence=confidence,
            model_provider="rule_based",
            model_name=SOP_RULE_ENGINE_NAME,
        )
        self._apply_model_enhancement(response, payload, current_user)
        return response

    def _resolve_generation_context(self, payload: SOPGenerateRequest) -> dict:
        device = self._resolve_device(payload.device_id)
        diagnosis = self._resolve_diagnosis(payload.diagnosis_trace_id)
        if device and diagnosis and diagnosis.device_id and diagnosis.device_id != device.id:
            raise SOPServiceError("Selected diagnosis record does not belong to selected device")

        manufacturer = payload.manufacturer or (diagnosis.manufacturer if diagnosis else None)
        product_series = payload.product_series or (diagnosis.product_series if diagnosis else None)
        model = payload.model or (diagnosis.model if diagnosis else None)
        device_type = payload.device_type or "pv_inverter"
        fault_type = payload.fault_type or "unknown"
        alarm_code = payload.alarm_code or (diagnosis.alarm_code if diagnosis else None)

        if device:
            manufacturer = device.manufacturer
            product_series = device.product_series
            model = device.model
            device_type = device.device_type
        if diagnosis and diagnosis.fault_type:
            fault_type = diagnosis.fault_type

        fault_type = self.rule_engine.normalize_fault_type(fault_type)
        maintenance_level = payload.maintenance_level or "level_2"
        self._validate_scope(
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            fault_type=fault_type,
            maintenance_level=maintenance_level,
            status=None,
        )
        if not manufacturer:
            raise SOPServiceError("manufacturer is required when no device or diagnosis record provides it")
        return {
            "device": device,
            "diagnosis": diagnosis,
            "manufacturer": manufacturer,
            "product_series": product_series,
            "model": model,
            "device_type": device_type,
            "fault_type": fault_type,
            "alarm_code": alarm_code,
            "maintenance_level": maintenance_level,
        }

    def _apply_model_enhancement(
        self,
        response: SOPGenerateResponse,
        payload: SOPGenerateRequest,
        current_user: User,
    ) -> None:
        if not payload.enable_model_enhancement:
            return
        prompt = self.prompt_builder.build_sop_prompt(
            request_summary={
                "device_id": str(payload.device_id) if payload.device_id else None,
                "diagnosis_trace_id": payload.diagnosis_trace_id,
                "manufacturer": payload.manufacturer,
                "product_series": payload.product_series,
                "model": payload.model,
                "device_type": payload.device_type,
                "fault_type": payload.fault_type,
                "alarm_code": payload.alarm_code,
                "maintenance_level": payload.maintenance_level,
            },
            source=response.source,
            title=response.title,
            steps=response.steps,
            safety_requirements=response.safety_requirements,
            tools_required=response.tools_required,
            materials_required=response.materials_required,
            compliance_notes=response.compliance_notes,
            references=response.references,
            media_context=response.media_items,
            kg_context=response.kg_context,
        )
        enhancement = ModelEnhancementService(self.db).enhance(
            prompt=prompt,
            task_type="sop",
            requested_provider=payload.model_provider,
            allow_fallback=payload.allow_model_fallback,
            current_user=current_user,
            default_provider="rule_based",
            default_model_name=SOP_RULE_ENGINE_NAME,
        )
        if enhancement.content:
            prefix = response.compliance_notes.strip() if response.compliance_notes else ""
            response.compliance_notes = (
                f"{prefix}\n\n模型增强说明：\n{enhancement.content}" if prefix else enhancement.content
            )
        ModelEnhancementService.apply_metadata(response, enhancement)

    def _resolve_kg_context(
        self,
        payload: SOPGenerateRequest,
        resolved: dict,
        current_user: User,
    ) -> dict:
        if not payload.enable_kg_enhancement:
            return {}
        diagnosis = resolved.get("diagnosis")
        question_parts = [
            resolved.get("fault_type"),
            resolved.get("alarm_code"),
            getattr(diagnosis, "fault_description", None),
            " ".join(getattr(diagnosis, "inspection_steps", []) or []) if diagnosis else None,
            " ".join(getattr(diagnosis, "recommended_actions", []) or []) if diagnosis else None,
        ]
        return KnowledgeGraphService(self.db).business_context(
            current_user=current_user,
            device_id=payload.device_id,
            manufacturer=resolved.get("manufacturer"),
            product_series=resolved.get("product_series"),
            fault_type=resolved.get("fault_type"),
            alarm_code=resolved.get("alarm_code"),
            question="\n".join(str(part) for part in question_parts if part),
            diagnosis_trace_id=payload.diagnosis_trace_id,
        )

    def _resolve_device(self, device_id: UUID | None) -> Device | None:
        if not device_id:
            return None
        device = self.repository.get_device(device_id)
        if not device:
            raise SOPServiceError("Device not found")
        if device.device_type != "pv_inverter":
            raise SOPServiceError("device_type must be pv_inverter")
        return device

    def _resolve_diagnosis(self, trace_id: str | None) -> DiagnosisRecord | None:
        if not trace_id:
            return None
        diagnosis = self.repository.get_diagnosis_by_trace_id(trace_id)
        if not diagnosis:
            raise SOPServiceError("Diagnosis record not found")
        return diagnosis

    def _diagnosis_media_context(self, diagnosis: DiagnosisRecord | None) -> list:
        if not diagnosis or not diagnosis.media_ids:
            return []
        try:
            media_items = self.media_service.resolve_media_items(
                [UUID(str(item)) for item in diagnosis.media_ids],
                device_id=diagnosis.device_id,
            )
        except (ValueError, MediaServiceError) as exc:
            raise SOPServiceError(f"Diagnosis media could not be resolved: {exc}") from exc
        return [self.media_service.media_context(item) for item in media_items]

    @staticmethod
    def _media_notice(media_items: list) -> str | None:
        if not media_items:
            return None
        return (
            "该规程关联了诊断现场图片；当前未启用 OCR/图像识别，图片仅作为人工查看的作业证据。"
        )

    def _resolve_references(
        self,
        *,
        diagnosis: DiagnosisRecord | None,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str,
        fault_type: str | None,
        alarm_code: str | None,
        include_references: bool,
    ) -> list[dict]:
        if not include_references:
            return []
        diagnosis_refs = self._references_from_diagnosis(diagnosis)
        if diagnosis_refs:
            return diagnosis_refs[:5]

        keywords = self._reference_keywords(
            manufacturer=manufacturer,
            product_series=product_series,
            fault_type=fault_type,
            alarm_code=alarm_code,
        )
        candidates = self.repository.search_reference_chunks(
            keywords=keywords,
            manufacturer=manufacturer,
            product_series=product_series,
            device_type=device_type,
            fault_type=fault_type,
            alarm_code=alarm_code,
            limit=5,
        )
        scored = []
        for chunk, document in candidates:
            score = self._score_reference(chunk, document, keywords, fault_type, alarm_code)
            if score > 0:
                scored.append((score, chunk, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [self._reference_from_chunk(chunk, document, score) for score, chunk, document in scored[:5]]

    @staticmethod
    def _references_from_diagnosis(diagnosis: DiagnosisRecord | None) -> list[dict]:
        if not diagnosis:
            return []
        references = diagnosis.references or []
        cleaned: list[dict] = []
        for reference in references:
            if not isinstance(reference, dict):
                continue
            if not reference.get("document_id") or not reference.get("chunk_id"):
                continue
            cleaned.append(SOPReference(**reference).model_dump(mode="json"))
        return cleaned

    @staticmethod
    def _reference_keywords(
        *,
        manufacturer: str | None,
        product_series: str | None,
        fault_type: str | None,
        alarm_code: str | None,
    ) -> list[str]:
        terms = [manufacturer, product_series, fault_type, alarm_code, "逆变器", "检修", "告警"]
        domain_terms = {
            "low_insulation": ["绝缘", "低绝缘", "阻抗", "对地"],
            "overtemperature": ["过温", "风扇", "散热", "温度"],
            "communication_fault": ["通信", "离线", "采集器", "RS485"],
            "mppt_low_power": ["MPPT", "低发电", "组串", "功率"],
            "grid_fault": ["电网", "并网", "过压", "欠压", "频率"],
            "alarm_code_query": ["告警码", "告警代码", "处理建议"],
        }
        terms.extend(domain_terms.get(fault_type or "", []))
        result: list[str] = []
        for term in terms:
            if term and term not in result:
                result.append(term)
        return result

    @staticmethod
    def _score_reference(
        chunk: KnowledgeChunk,
        document: KnowledgeDocument,
        keywords: list[str],
        fault_type: str | None,
        alarm_code: str | None,
    ) -> float:
        content = chunk.content or ""
        section_title = chunk.section_title or ""
        document_title = document.title or ""
        document_summary = document.summary or ""
        score = 0.0
        for keyword in keywords:
            if len(keyword) < 2:
                continue
            score += min(SOPService._hit_count(content, keyword), 4) * 2.0
            score += min(SOPService._hit_count(section_title, keyword), 2) * 4.0
            score += min(SOPService._hit_count(document_title, keyword), 2) * 4.0
            score += min(SOPService._hit_count(document_summary, keyword), 2) * 1.5
        if fault_type and fault_type in str(document.metadata_json or {}):
            score += 2.0
        if alarm_code and alarm_code.lower() in content.lower():
            score += 8.0
        if document.document_type in {"manual", "alarm_code", "sop", "fault_case"}:
            score += 1.0
        return round(score, 2)

    @staticmethod
    def _reference_from_chunk(chunk: KnowledgeChunk, document: KnowledgeDocument, score: float) -> dict:
        return SOPReference(
            document_id=document.id,
            document_title=document.title,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            quote=SOPService._quote(chunk.content),
            manufacturer=document.manufacturer,
            product_series=document.product_series,
            device_type=document.device_type,
            document_type=document.document_type,
            source=document.source,
            score=score,
        ).model_dump(mode="json")

    @staticmethod
    def _quote(content: str) -> str:
        compact = re.sub(r"\s+", " ", content).strip()
        return compact[:180]

    @staticmethod
    def _hit_count(text: str, keyword: str) -> int:
        if not text or not keyword:
            return 0
        return len(re.findall(re.escape(keyword.lower()), text.lower()))

    @staticmethod
    def _confidence(*, source: str, references: list[dict], base: float | None = None) -> float:
        confidence = 0.68 if source == "template" else (base or 0.52)
        if references:
            confidence += min(len(references), 5) * 0.03
        else:
            confidence -= 0.08
        return round(max(0.28, min(confidence, 0.86)), 2)

    @staticmethod
    def _template_payload(template: SOPTemplate) -> dict:
        return SOPTemplateRead.model_validate(template).model_dump(mode="json")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise SOPServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise SOPServiceError("page_size must be between 1 and 100")

    @staticmethod
    def _validate_scope(
        *,
        manufacturer: str | None,
        product_series: str | None,
        device_type: str | None,
        fault_type: str | None,
        maintenance_level: str | None,
        status: str | None,
    ) -> None:
        if manufacturer and manufacturer not in ALLOWED_SOP_MANUFACTURERS:
            raise SOPServiceError("manufacturer must be huawei or sungrow")
        if product_series and product_series not in ALLOWED_SOP_PRODUCT_SERIES:
            raise SOPServiceError("unsupported product_series")
        if manufacturer == "huawei" and product_series not in {None, "SUN2000", "FusionSolar", "other"}:
            raise SOPServiceError("huawei SOP supports SUN2000 or FusionSolar product_series")
        if manufacturer == "sungrow" and product_series not in {None, "SG", "other"}:
            raise SOPServiceError("sungrow SOP supports SG product_series")
        if device_type and device_type not in ALLOWED_SOP_DEVICE_TYPES:
            raise SOPServiceError("device_type must be pv_inverter")
        if fault_type and fault_type not in ALLOWED_SOP_FAULT_TYPES:
            raise SOPServiceError("unsupported fault_type")
        if maintenance_level and maintenance_level not in ALLOWED_SOP_MAINTENANCE_LEVELS:
            raise SOPServiceError("unsupported maintenance_level")
        if status and status not in ALLOWED_SOP_TEMPLATE_STATUSES:
            raise SOPServiceError("unsupported template status")
