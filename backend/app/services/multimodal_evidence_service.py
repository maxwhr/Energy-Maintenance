from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User
from app.core.config import get_settings
from app.models.multimodal_evidence import (
    MediaAIAnalysis,
    MediaEvidenceLink,
    MediaOCRResult,
    MediaProcessingJob,
)
from app.repositories.multimodal_evidence_repository import MultimodalEvidenceRepository
from app.schemas.multimodal_evidence import (
    MediaAIAnalysisCreate,
    MediaAIAnalysisRead,
    MediaAIAnalysisReview,
    MediaEvidenceLinkCreate,
    MediaEvidenceLinkRead,
    MediaMultimodalSummary,
    MediaOCRResultRead,
    MediaProcessingJobCreate,
    MediaProcessingJobRead,
)
from app.services.external_api_gateway import ExternalApiGateway, ExternalApiGatewayError
from app.services.media_service import MediaService, MediaServiceError
from app.services.multimodal_result_normalizer import MultimodalResultNormalizer


JOB_TYPES = {"ocr", "multimodal_analysis", "combined", "manual_review"}
JOB_STATUSES = {"pending", "running", "succeeded", "failed", "blocked", "cancelled"}
ANALYSIS_TYPES = {"fault_scene", "nameplate", "alarm_screen", "wiring", "document_photo", "general", "unknown"}
REVIEW_STATUSES = {"pending", "accepted", "rejected", "revised"}
SOURCE_TYPES = {
    "retrieval",
    "diagnosis",
    "sop",
    "maintenance_task",
    "knowledge_contribution",
    "knowledge_document",
    "record_center",
    "agent_run",
    "agent_artifact",
    "correction",
}
RELATION_TYPES = {"used_as_context", "generated_from", "reviewed_into", "attached_to", "supports", "contradicts"}


class MultimodalEvidenceServiceError(ValueError):
    pass


class MultimodalEvidenceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MultimodalEvidenceRepository(db)
        self.gateway = ExternalApiGateway(db)

    def create_processing_job(
        self,
        media_id: UUID,
        payload: MediaProcessingJobCreate,
        current_user: User,
    ) -> MediaProcessingJobRead:
        self._ensure_media(media_id)
        if payload.job_type not in JOB_TYPES:
            raise MultimodalEvidenceServiceError("Invalid job_type")
        if payload.mock_run and current_user.role not in {"admin", "expert"}:
            raise MultimodalEvidenceServiceError("Permission denied for mock_run")
        if payload.real_run and current_user.role not in {"admin", "expert"}:
            raise MultimodalEvidenceServiceError("Permission denied for real_run")
        if payload.real_run and payload.mock_run:
            raise MultimodalEvidenceServiceError("real_run and mock_run cannot be used together")

        raw_input = payload.input_summary
        if payload.real_run and payload.job_type in {"ocr", "multimodal_analysis"}:
            raw_input = self._with_media_image_input(media_id, raw_input)
        sanitized_input = self.gateway.sanitize_summary(raw_input)
        capability = self._capability_for_job(payload)
        job_payload = {
            "media_id": str(media_id),
            "job_type": payload.job_type,
            "provider_code": payload.provider_code,
            "capability": capability,
            "analysis_type": payload.analysis_type,
            "dry_run": payload.dry_run,
            "mock_run": payload.mock_run,
            "real_run": payload.real_run,
            "input_summary": sanitized_input,
            "agent_run_id": payload.agent_run_id,
        }
        gateway_payload = {**job_payload, "input_summary": raw_input}
        gateway_result = None
        if payload.job_type == "ocr":
            gateway_result = self._gateway_real_run(
                tool_name="media_ocr",
                capability=capability,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=gateway_payload,
                provider_code=payload.provider_code,
            ) if payload.real_run else self._gateway_mock_run(
                tool_name="media_ocr",
                capability=capability,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=gateway_payload,
                provider_code=payload.provider_code,
            ) if payload.mock_run else self._gateway_dry_run(
                tool_name="media_ocr",
                capability=capability,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=gateway_payload,
                provider_code=payload.provider_code,
            )
            job = self._job_from_gateway(
                media_id=media_id,
                job_type="ocr",
                gateway_result=gateway_result,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=job_payload,
                default_error_code="ocr_disabled",
            )
        elif payload.job_type == "multimodal_analysis":
            gateway_result = self._gateway_real_run(
                tool_name="media_mimo_analysis",
                capability=capability,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=gateway_payload,
                provider_code=payload.provider_code,
            ) if payload.real_run else self._gateway_mock_run(
                tool_name="media_mimo_analysis",
                capability=capability,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=gateway_payload,
                provider_code=payload.provider_code,
            ) if payload.mock_run else self._gateway_dry_run(
                tool_name="media_mimo_analysis",
                capability=capability,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=gateway_payload,
                provider_code=payload.provider_code,
            )
            job = self._job_from_gateway(
                media_id=media_id,
                job_type="multimodal_analysis",
                gateway_result=gateway_result,
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary=job_payload,
                default_error_code="mimo_not_configured",
                default_error_message="mimo-2.5 adapter is reserved but not configured",
            )
        elif payload.job_type == "combined":
            ocr_result = self._gateway_dry_run(
                tool_name="media_ocr",
                capability="ocr",
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary={**job_payload, "combined_part": "ocr"},
                provider_code=None,
            )
            mimo_result = self._gateway_dry_run(
                tool_name="media_mimo_analysis",
                capability="fault_scene_analysis",
                current_user=current_user,
                agent_run_id=payload.agent_run_id,
                input_summary={**job_payload, "combined_part": "multimodal_analysis"},
                provider_code=None,
            )
            job = MediaProcessingJob(
                media_id=media_id,
                job_type="combined",
                provider_code="system",
                provider_name="Provider Gateway",
                model_name=None,
                status="blocked",
                input_hash=self._hash_payload(job_payload),
                progress=0,
                error_code="providers_not_configured",
                error_message="OCR and multimodal providers are not configured for real execution.",
                request_summary_json=self.gateway.sanitize_summary(job_payload),
                result_summary_json={
                    "ocr": ocr_result.model_dump(mode="json"),
                    "multimodal_analysis": mimo_result.model_dump(mode="json"),
                    "external_api_called": False,
                },
                external_trace_id=ocr_result.trace_id,
                agent_run_id=payload.agent_run_id,
                created_by=current_user.id,
                finished_at=self._now(),
            )
        else:
            job = MediaProcessingJob(
                media_id=media_id,
                job_type="manual_review",
                provider_code=payload.provider_code or "manual",
                provider_name="Manual review",
                model_name=None,
                status="pending",
                input_hash=self._hash_payload(job_payload),
                progress=0,
                request_summary_json=self.gateway.sanitize_summary(job_payload),
                result_summary_json={"external_api_called": False, "manual_review": True},
                agent_run_id=payload.agent_run_id,
                created_by=current_user.id,
            )

        try:
            saved = self.repository.create_job(job)
            persisted_result = None
            if (payload.mock_run or payload.real_run) and gateway_result and saved.status == "succeeded":
                if payload.job_type == "ocr":
                    persisted_result = self._create_ocr_result(
                        media_id,
                        saved,
                        gateway_result,
                        current_user,
                        mocked=payload.mock_run,
                    )
                    result_id = str(persisted_result.id)
                    result_type = "media_ocr_results"
                elif payload.job_type == "multimodal_analysis":
                    persisted_result = self._create_ai_analysis(
                        media_id,
                        saved,
                        gateway_result,
                        current_user,
                        payload.analysis_type or "fault_scene",
                        mocked=payload.mock_run,
                    )
                    result_id = str(persisted_result.id)
                    result_type = "media_ai_analyses"
                else:
                    result_id = None
                    result_type = None
                if result_id:
                    saved.result_summary_json = {
                        **(saved.result_summary_json or {}),
                        "persisted_result_type": result_type,
                        "persisted_result_id": result_id,
                        "mocked": payload.mock_run,
                        "real_external_api_used": payload.real_run,
                        "not_for_production": payload.mock_run,
                    }
                    self.repository.update_job(saved)
            self.db.commit()
            return MediaProcessingJobRead.model_validate(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MultimodalEvidenceServiceError(f"Media processing job write failed: {exc}") from exc

    def get_job(self, job_id: UUID) -> MediaProcessingJobRead | None:
        item = self.repository.get_job(job_id)
        return MediaProcessingJobRead.model_validate(item) if item else None

    def list_jobs_by_media(
        self,
        media_id: UUID,
        *,
        job_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._ensure_media(media_id)
        self._validate_page(page, page_size)
        items, total = self.repository.list_jobs_by_media(
            media_id,
            job_type=job_type,
            status=status,
            page=page,
            page_size=page_size,
        )
        return self._page([MediaProcessingJobRead.model_validate(item).model_dump(mode="json") for item in items], total, page, page_size)

    def cancel_job(self, job_id: UUID, current_user: User) -> MediaProcessingJobRead:
        job = self.repository.get_job(job_id)
        if not job:
            raise MultimodalEvidenceServiceError("Media processing job not found")
        if job.status in {"succeeded", "failed", "cancelled", "blocked"}:
            raise MultimodalEvidenceServiceError("Only pending or running jobs can be cancelled")
        job.status = "cancelled"
        job.finished_at = self._now()
        job.error_code = "cancelled_by_user"
        job.error_message = f"Cancelled by {current_user.username}"
        try:
            saved = self.repository.update_job(job)
            self.db.commit()
            return MediaProcessingJobRead.model_validate(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MultimodalEvidenceServiceError(f"Media processing job cancel failed: {exc}") from exc

    def list_ocr_results(
        self,
        media_id: UUID,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._ensure_media(media_id)
        self._validate_page(page, page_size)
        items, total = self.repository.list_ocr_results(media_id, status=status, page=page, page_size=page_size)
        return self._page([MediaOCRResultRead.model_validate(item).model_dump(mode="json") for item in items], total, page, page_size)

    def get_ocr_result(self, result_id: UUID) -> MediaOCRResultRead | None:
        item = self.repository.get_ocr_result(result_id)
        return MediaOCRResultRead.model_validate(item) if item else None

    def list_ai_analyses(
        self,
        media_id: UUID,
        *,
        human_review_status: str | None = None,
        analysis_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._ensure_media(media_id)
        self._validate_page(page, page_size)
        items, total = self.repository.list_ai_analyses(
            media_id,
            human_review_status=human_review_status,
            analysis_type=analysis_type,
            page=page,
            page_size=page_size,
        )
        return self._page([MediaAIAnalysisRead.model_validate(item).model_dump(mode="json") for item in items], total, page, page_size)

    def get_ai_analysis(self, analysis_id: UUID) -> MediaAIAnalysisRead | None:
        item = self.repository.get_ai_analysis(analysis_id)
        return MediaAIAnalysisRead.model_validate(item) if item else None

    def review_ai_analysis(
        self,
        analysis_id: UUID,
        payload: MediaAIAnalysisReview,
        current_user: User,
    ) -> MediaAIAnalysisRead:
        if payload.review_status not in REVIEW_STATUSES:
            raise MultimodalEvidenceServiceError("Invalid review status")
        analysis = self.repository.get_ai_analysis(analysis_id)
        if not analysis:
            raise MultimodalEvidenceServiceError("AI analysis not found")
        analysis.human_review_status = payload.review_status
        analysis.reviewed_by = current_user.id
        analysis.reviewed_at = self._now()
        analysis.review_comment = payload.review_comment
        try:
            saved = self.repository.update_ai_analysis(analysis)
            self.db.commit()
            return MediaAIAnalysisRead.model_validate(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MultimodalEvidenceServiceError(f"AI analysis review failed: {exc}") from exc

    def create_evidence_link(
        self,
        payload: MediaEvidenceLinkCreate,
        current_user: User,
    ) -> MediaEvidenceLinkRead:
        self._ensure_media(payload.media_id)
        if payload.source_type not in SOURCE_TYPES:
            raise MultimodalEvidenceServiceError("Invalid source_type")
        if payload.relation_type not in RELATION_TYPES:
            raise MultimodalEvidenceServiceError("Invalid relation_type")
        if payload.ocr_result_id and not self.repository.get_ocr_result(payload.ocr_result_id):
            raise MultimodalEvidenceServiceError("OCR result not found")
        if payload.analysis_id and not self.repository.get_ai_analysis(payload.analysis_id):
            raise MultimodalEvidenceServiceError("AI analysis not found")
        link = MediaEvidenceLink(
            media_id=payload.media_id,
            ocr_result_id=payload.ocr_result_id,
            analysis_id=payload.analysis_id,
            source_type=payload.source_type,
            source_id=payload.source_id,
            relation_type=payload.relation_type,
            created_at=self._now(),
            created_by=current_user.id,
        )
        try:
            saved = self.repository.create_evidence_link(link)
            self.db.commit()
            return MediaEvidenceLinkRead.model_validate(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MultimodalEvidenceServiceError(f"Evidence link write failed: {exc}") from exc

    def list_evidence_links(
        self,
        *,
        media_id: UUID | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        self._validate_page(page, page_size)
        items, total = self.repository.list_evidence_links(
            media_id=media_id,
            source_type=source_type,
            source_id=source_id,
            page=page,
            page_size=page_size,
        )
        return self._page([MediaEvidenceLinkRead.model_validate(item).model_dump(mode="json") for item in items], total, page, page_size)

    def get_media_multimodal_summary(self, media_id: UUID) -> MediaMultimodalSummary:
        self._ensure_media(media_id)
        jobs, _ = self.repository.list_jobs_by_media(media_id, page=1, page_size=50)
        ocr_results, _ = self.repository.list_ocr_results(media_id, page=1, page_size=50)
        analyses, _ = self.repository.list_ai_analyses(media_id, page=1, page_size=50)
        links, _ = self.repository.list_evidence_links(media_id=media_id, page=1, page_size=50)
        provider_status = self.gateway.status().model_dump(mode="json")
        latest_ocr = ocr_results[0].status if ocr_results else None
        latest_analysis = analyses[0].human_review_status if analyses else None
        return MediaMultimodalSummary(
            media_id=media_id,
            jobs=[MediaProcessingJobRead.model_validate(item) for item in jobs],
            ocr_results=[MediaOCRResultRead.model_validate(item) for item in ocr_results],
            analyses=[MediaAIAnalysisRead.model_validate(item) for item in analyses],
            evidence_links=[MediaEvidenceLinkRead.model_validate(item) for item in links],
            provider_status=provider_status,
            latest_ocr_status=latest_ocr,
            latest_analysis_status=latest_analysis,
        )

    def create_manual_ai_analysis_for_test_or_review(
        self,
        payload: MediaAIAnalysisCreate,
        current_user: User,
    ) -> MediaAIAnalysisRead:
        self._ensure_media(payload.media_id)
        if payload.analysis_type not in ANALYSIS_TYPES:
            raise MultimodalEvidenceServiceError("Invalid analysis_type")
        if payload.job_id and not self.repository.get_job(payload.job_id):
            raise MultimodalEvidenceServiceError("Media processing job not found")
        analysis = MediaAIAnalysis(
            media_id=payload.media_id,
            job_id=payload.job_id,
            provider_code=payload.provider_code,
            provider_name=payload.provider_name,
            model_name=payload.model_name,
            analysis_type=payload.analysis_type,
            summary=payload.summary,
            detected_text=payload.detected_text,
            detected_alarm_codes_json=payload.detected_alarm_codes_json,
            detected_device_info_json=payload.detected_device_info_json,
            visual_findings_json=payload.visual_findings_json,
            possible_faults_json=payload.possible_faults_json,
            safety_risks_json=payload.safety_risks_json,
            recommended_actions_json=payload.recommended_actions_json,
            limitations_json=payload.limitations_json,
            confidence=payload.confidence,
            raw_response_json={
                **payload.raw_response_json,
                "manual_or_rule_based": True,
                "external_api_called": False,
            },
            external_trace_id=None,
            human_review_status="pending",
            created_by=current_user.id,
        )
        try:
            saved = self.repository.create_ai_analysis(analysis)
            self.db.commit()
            return MediaAIAnalysisRead.model_validate(saved)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MultimodalEvidenceServiceError(f"Manual AI analysis write failed: {exc}") from exc

    def latest_ocr_context(self, media_id: UUID) -> dict[str, Any] | None:
        result = self.repository.latest_ocr_result(media_id, status="succeeded")
        if not result:
            return None
        return MediaOCRResultRead.model_validate(result).model_dump(mode="json")

    def latest_ai_analysis_context(self, media_id: UUID) -> dict[str, Any] | None:
        analysis = self.repository.latest_ai_analysis(media_id, human_review_status="accepted")
        if not analysis:
            analysis = self.repository.latest_ai_analysis(media_id, human_review_status="pending")
        if not analysis:
            return None
        return MediaAIAnalysisRead.model_validate(analysis).model_dump(mode="json")

    def latest_job_status(self, media_id: UUID, job_type: str | None = None) -> dict[str, Any] | None:
        items, _ = self.repository.list_jobs_by_media(media_id, job_type=job_type, page=1, page_size=1)
        if not items:
            return None
        return MediaProcessingJobRead.model_validate(items[0]).model_dump(mode="json")

    def _job_from_gateway(
        self,
        *,
        media_id: UUID,
        job_type: str,
        gateway_result: Any,
        current_user: User,
        agent_run_id: str | None,
        input_summary: dict[str, Any],
        default_error_code: str,
        default_error_message: str | None = None,
    ) -> MediaProcessingJob:
        result = gateway_result.model_dump(mode="json")
        provider_code = result.get("provider_code") or "unknown"
        status = result.get("status")
        if status in {"mocked", "succeeded"} and result.get("success"):
            job_status = "succeeded"
        elif status == "failed":
            job_status = "failed"
        elif status in {"blocked", "disabled", "not_configured", "configured_but_real_call_not_allowed"}:
            job_status = "blocked"
        else:
            job_status = "pending"
        return MediaProcessingJob(
            media_id=media_id,
            job_type=job_type,
            provider_code=provider_code,
            provider_name=provider_code,
            model_name=result.get("model_name"),
            status=job_status,
            input_hash=self._hash_payload(input_summary),
            progress=100 if job_status == "succeeded" else 0,
            error_code=None if job_status == "succeeded" else result.get("blocked_reason") or default_error_code,
            error_message=None if job_status == "succeeded" else default_error_message or result.get("message"),
            request_summary_json=self.gateway.sanitize_summary(input_summary),
            result_summary_json={
                "external_api_gateway": result,
                "external_api_called": bool(result.get("external_api_called")),
                "mocked": status == "mocked",
                "not_for_production": status == "mocked",
                "machine_result_boundary": (
                    "Mock-run result is local contract evidence only."
                    if status == "mocked"
                    else "Real provider result is auxiliary evidence and requires human review."
                    if status == "succeeded"
                    else "No machine recognition result was produced."
                ),
            },
            external_trace_id=result.get("trace_id"),
            agent_run_id=agent_run_id,
            created_by=current_user.id,
            finished_at=self._now(),
        )

    def _create_ocr_result(
        self,
        media_id: UUID,
        job: MediaProcessingJob,
        gateway_result: Any,
        current_user: User,
        *,
        mocked: bool,
    ) -> MediaOCRResult:
        result = gateway_result.model_dump(mode="json")
        normalized = MultimodalResultNormalizer.normalize_ocr(result.get("normalized_result") or {})
        ocr = MediaOCRResult(
            media_id=media_id,
            job_id=job.id,
            provider_code=result.get("provider_code") or "mock_provider",
            provider_name=result.get("provider_code") or "mock_provider",
            model_name=result.get("model_name"),
            language=normalized.get("language") or "chi_sim+eng",
            text=normalized.get("text") or "",
            confidence=normalized.get("confidence") or 0.0,
            regions_json=normalized.get("regions") or [],
            raw_result_json={
                "normalized_result": normalized,
                "mocked": mocked,
                "not_for_production": mocked,
                "real_external_api_used": not mocked,
                "external_api_called": bool(result.get("external_api_called")),
                "external_api_gateway_trace_id": result.get("trace_id"),
            },
            status="succeeded",
            external_trace_id=result.get("trace_id"),
            created_by=current_user.id,
            created_at=self._now(),
        )
        return self.repository.create_ocr_result(ocr)

    def _create_ai_analysis(
        self,
        media_id: UUID,
        job: MediaProcessingJob,
        gateway_result: Any,
        current_user: User,
        analysis_type: str,
        *,
        mocked: bool,
    ) -> MediaAIAnalysis:
        result = gateway_result.model_dump(mode="json")
        normalized = MultimodalResultNormalizer.normalize_multimodal(
            str(result.get("capability") or "fault_scene_analysis"),
            result.get("normalized_result") or {},
        )
        analysis = MediaAIAnalysis(
            media_id=media_id,
            job_id=job.id,
            provider_code=result.get("provider_code") or "mock_provider",
            provider_name=result.get("provider_code") or "mock_provider",
            model_name=result.get("model_name"),
            analysis_type=analysis_type,
            summary=normalized.get("summary")
            or (
                "Task 22E mocked multimodal analysis result; no real external API was called."
                if mocked
                else "Real multimodal provider returned auxiliary analysis; human review is required."
            ),
            detected_text="\n".join(str(item) for item in normalized.get("visible_text") or []),
            detected_alarm_codes_json=normalized.get("detected_alarm_codes") or [],
            detected_device_info_json=normalized.get("detected_device_info") or {},
            visual_findings_json=normalized.get("visual_findings") or [],
            possible_faults_json=normalized.get("possible_fault_clues") or [],
            safety_risks_json=normalized.get("safety_risks") or [],
            recommended_actions_json=[{"action": item} for item in normalized.get("recommended_next_steps") or []],
            limitations_json=normalized.get("limitations") or [],
            confidence=normalized.get("confidence") or 0.0,
            raw_response_json={
                "normalized_result": normalized,
                "mocked": mocked,
                "not_for_production": mocked,
                "real_external_api_used": not mocked,
                "external_api_called": bool(result.get("external_api_called")),
                "external_api_gateway_trace_id": result.get("trace_id"),
            },
            external_trace_id=result.get("trace_id"),
            human_review_status="pending",
            created_by=current_user.id,
        )
        return self.repository.create_ai_analysis(analysis)

    def _create_mock_ocr_result(
        self,
        media_id: UUID,
        job: MediaProcessingJob,
        gateway_result: Any,
        current_user: User,
    ) -> MediaOCRResult:
        return self._create_ocr_result(media_id, job, gateway_result, current_user, mocked=True)

    def _create_mock_ai_analysis(
        self,
        media_id: UUID,
        job: MediaProcessingJob,
        gateway_result: Any,
        current_user: User,
        analysis_type: str,
    ) -> MediaAIAnalysis:
        return self._create_ai_analysis(media_id, job, gateway_result, current_user, analysis_type, mocked=True)

    def _gateway_dry_run(
        self,
        *,
        tool_name: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        agent_run_id: str | None,
        provider_code: str | None = None,
    ) -> Any:
        try:
            if provider_code:
                return self.gateway.dry_run_provider(
                    provider_code=provider_code,
                    capability=capability,
                    current_user=current_user,
                    payload=input_summary,
                )
            return self.gateway.dry_run_for_tool(
                tool_name=tool_name,
                capability=capability,
                current_user=current_user,
                agent_run_id=agent_run_id,
                input_summary=input_summary,
            )
        except ExternalApiGatewayError as exc:
            raise MultimodalEvidenceServiceError(str(exc)) from exc

    def _gateway_mock_run(
        self,
        *,
        tool_name: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        agent_run_id: str | None,
        provider_code: str | None = None,
    ) -> Any:
        try:
            if provider_code:
                return self.gateway.mock_run_provider(
                    provider_code=provider_code,
                    capability=capability,
                    current_user=current_user,
                    payload=input_summary,
                )
            return self.gateway.mock_run_for_tool(
                tool_name=tool_name,
                capability=capability,
                current_user=current_user,
                agent_run_id=agent_run_id,
                input_summary=input_summary,
            )
        except ExternalApiGatewayError as exc:
            raise MultimodalEvidenceServiceError(str(exc)) from exc

    def _gateway_real_run(
        self,
        *,
        tool_name: str,
        capability: str,
        current_user: User,
        input_summary: dict[str, Any],
        agent_run_id: str | None,
        provider_code: str | None = None,
    ) -> Any:
        try:
            if provider_code:
                return self.gateway.real_run_provider(
                    provider_code=provider_code,
                    capability=capability,
                    current_user=current_user,
                    payload=input_summary,
                )
            return self.gateway.real_run_for_tool(
                tool_name=tool_name,
                capability=capability,
                current_user=current_user,
                agent_run_id=agent_run_id,
                input_summary=input_summary,
            )
        except ExternalApiGatewayError as exc:
            raise MultimodalEvidenceServiceError(str(exc)) from exc

    @staticmethod
    def _capability_for_job(payload: MediaProcessingJobCreate) -> str:
        if payload.capability:
            return payload.capability
        if payload.job_type == "ocr":
            return "ocr"
        if payload.job_type == "multimodal_analysis":
            if payload.analysis_type == "nameplate":
                return "nameplate_extract"
            if payload.analysis_type == "alarm_screen":
                return "alarm_screen_analysis"
            return "fault_scene_analysis"
        return "structured_extract"

    def _ensure_media(self, media_id: UUID) -> None:
        media = self.repository.get_media(media_id)
        if not media:
            raise MultimodalEvidenceServiceError("Media item not found")
        if media.status == "archived":
            raise MultimodalEvidenceServiceError("Media item is archived")

    def _with_media_image_input(self, media_id: UUID, raw_input: dict[str, Any]) -> dict[str, Any]:
        if raw_input.get("image_base64") or raw_input.get("images"):
            return raw_input
        service = MediaService(self.db)
        media = service.get_media(media_id)
        if not media:
            raise MultimodalEvidenceServiceError("Media item not found")
        try:
            path = service.resolve_file_path(media)
            content = path.read_bytes()
        except (MediaServiceError, OSError) as exc:
            raise MultimodalEvidenceServiceError(f"Media content is unavailable for real-run: {exc}") from exc
        max_bytes = get_settings().OCR_MAX_IMAGE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise MultimodalEvidenceServiceError("Media image exceeds real-run size limit")
        return {
            **raw_input,
            "image_base64": base64.b64encode(content).decode("ascii"),
            "mime_type": media.mime_type or "image/png",
            "image_count": 1,
            "file_size": media.file_size or len(content),
            "media_id": str(media_id),
        }

    @staticmethod
    def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _hash_payload(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1:
            raise MultimodalEvidenceServiceError("page must be greater than or equal to 1")
        if page_size < 1 or page_size > 100:
            raise MultimodalEvidenceServiceError("page_size must be between 1 and 100")
