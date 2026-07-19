from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentRun,
    MultimodalDiagnosticHypothesis,
    MultimodalEvidenceConflict,
    MultimodalMaintenanceCase,
    UploadedMedia,
    User,
)
from app.repositories.multimodal_case_repository import MultimodalCaseRepository
from app.schemas.multimodal_case import (
    MultimodalAnalyzeRequest,
    MultimodalDiagnoseRequest,
    MultimodalEvidenceCreate,
    MultimodalRetrieveRequest,
    MultimodalSopDraftRequest,
    MultimodalTaskDraftRequest,
)
from app.schemas.multimodal_evidence import MediaProcessingJobCreate
from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
from app.services.cross_modal_retrieval_plan_service import CrossModalRetrievalPlanService
from app.services.cross_modal_retrieval_service import CrossModalRetrievalService
from app.services.image_preprocessing_service import ImagePreprocessingService
from app.services.media_service import MediaService
from app.services.multimodal_case_state_service import (
    MultimodalCaseError,
    MultimodalCasePermissionError,
    MultimodalCaseStateService,
)
from app.services.multimodal_clarification_service import MultimodalClarificationService
from app.services.multimodal_confidence_service import MultimodalConfidenceService
from app.services.multimodal_diagnosis_service import MultimodalDiagnosisService
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolutionService
from app.services.multimodal_evidence_conflict_service import MultimodalEvidenceConflictService
from app.services.multimodal_evidence_fusion_service import MultimodalEvidenceFusionService
from app.services.multimodal_evidence_service import MultimodalEvidenceService
from app.services.multimodal_safety_guard_service import MultimodalSafetyGuardService
from app.services.multimodal_sop_task_boundary_service import MultimodalSopTaskBoundaryService
from app.services.ocr_evidence_normalization_service import OcrEvidenceNormalizationService
from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.visual_signal_extraction_service import VisualSignalExtractionService


class MultimodalCaseOrchestratorError(ValueError):
    pass


class MultimodalCaseOrchestratorService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.repository = MultimodalCaseRepository(db)
        self.state = MultimodalCaseStateService(db)
        self.media = MediaService(db)

    def attach_media(self, case: MultimodalMaintenanceCase, media: UploadedMedia, user: User) -> dict:
        self._require_editor(user)
        if media.status == "archived":
            raise MultimodalCaseOrchestratorError("Archived media cannot be attached")
        if user.role not in {"admin", "expert"} and media.uploaded_by != user.id:
            raise MultimodalCasePermissionError("Cannot attach another user's media")
        media_ids = list(dict.fromkeys([*(case.media_ids or []), str(media.id)]))
        if len(media_ids) > self.settings.MULTIMODAL_MAX_MEDIA_PER_CASE:
            raise MultimodalCaseOrchestratorError(
                f"A case supports at most {self.settings.MULTIMODAL_MAX_MEDIA_PER_CASE} media items"
            )
        case.media_ids = media_ids
        self.repository.save_case(case)
        if case.status == "DRAFT":
            self.state.transition(case, "MEDIA_UPLOADED", user, reason="media_attached", detail={"media_id": str(media.id)})
        else:
            self.state.audit(case, user, "media_attached", detail={"media_id": str(media.id)})
        self.db.commit()
        return {
            "case_id": case.case_id,
            "media_id": str(media.id),
            "media_count": len(media_ids),
            "status": case.status,
            "preview_url": f"/api/media/{media.id}/content",
        }

    def list_media(self, case: MultimodalMaintenanceCase) -> list[dict]:
        ids = self._case_media_ids(case)
        return [self._public_media(item) for item in self.repository.get_media_items(ids)]

    def analyze(self, case: MultimodalMaintenanceCase, payload: MultimodalAnalyzeRequest, user: User) -> dict:
        self._require_editor(user)
        if payload.allow_real_api:
            self._require_real_provider_authorization(user)
        run_id = self._analysis_run_id(case, payload)
        existing = self.repository.get_agent_run(run_id)
        if existing and not payload.force:
            return self._analysis_response(case, existing, cached=True)
        run = AgentRun(
            run_id=run_id,
            agent_code="task25c_multimodal_case_analysis",
            user_id=user.id,
            device_id=case.device_id,
            status="QUEUED",
            input_text=None,
            input_media_ids_json=list(case.media_ids or []),
            context_json={
                "case_id": case.case_id,
                "dry_run": payload.dry_run,
                "mock_run": payload.mock_run,
                "allow_real_api": payload.allow_real_api,
                "external_payload_logged": False,
                "dedicated_rerank_status": "DEFERRED_QWEN3_RERANK_CONFIG",
            },
            provider="deterministic_task25c",
            model_name=None,
            requires_human_approval=False,
            started_at=datetime.now(timezone.utc),
        )
        self.repository.create_agent_run(run)
        case.analysis_job_ids = list(dict.fromkeys([*(case.analysis_job_ids or []), run_id]))
        self.repository.save_case(case)
        self.db.flush()
        try:
            if case.status != "ANALYZING":
                self.state.transition(case, "ANALYZING", user, reason="analysis_started", detail={"job_id": run_id})
            run.status = "RUNNING"
            self.repository.save_agent_run(run)
            media_items = self.repository.get_media_items(self._case_media_ids(case))
            preprocess_summaries = []
            provider_jobs = []
            for media in media_items:
                preprocess_summaries.append(self._preprocess_media(case, media, user))
                if payload.allow_real_api:
                    provider_jobs.extend(self._run_real_provider_jobs(media, run_id, user))
                self._ingest_existing_media_evidence(case, media, user)

            evidence = self.repository.list_evidence(case.case_id)
            bound_device = self.repository.get_device(case.device_id) if case.device_id else None
            resolution = MultimodalEntityResolutionService().resolve(case, evidence, bound_device=bound_device)
            conflict_candidates = MultimodalEvidenceConflictService().detect(evidence)
            conflicts = self._persist_conflicts(case, conflict_candidates)
            quality_flags = list(dict.fromkeys(
                flag for item in preprocess_summaries for flag in item.get("quality_flags", [])
            ))
            needs_ocr = any(item.get("ocr_ready") is False for item in preprocess_summaries)
            questions = MultimodalClarificationService().build(
                missing_information=resolution.missing_information,
                conflicts=[item.as_dict() for item in conflict_candidates],
                image_quality_flags=quality_flags,
                needs_ocr=needs_ocr,
            )
            self._apply_resolution(case, resolution.as_dict(), questions, preprocess_summaries)
            evidence = self.repository.list_evidence(case.case_id)
            target = "NEEDS_CLARIFICATION" if questions or any(item.resolution_required for item in conflicts) else (
                "EVIDENCE_READY" if evidence else "INSUFFICIENT_EVIDENCE"
            )
            self.state.transition(case, target, user, reason="analysis_completed", detail={
                "job_id": run_id,
                "evidence_count": len(evidence),
                "conflict_count": len(conflicts),
                "external_provider_jobs": len(provider_jobs),
            })
            run.status = "PARTIAL" if questions else "SUCCEEDED"
            run.finished_at = datetime.now(timezone.utc)
            run.final_answer = "Case evidence extraction completed; human verification remains required."
            run.confidence = Decimal(str(max(0.0, min(resolution.resolution_confidence, 0.99))))
            context = dict(run.context_json or {})
            context.update({
                "provider_job_ids": provider_jobs,
                "evidence_count": len(evidence),
                "conflict_count": len(conflicts),
                "question_count": len(questions),
                "external_api_called": bool(provider_jobs),
            })
            run.context_json = context
            self.repository.save_agent_run(run)
            self.db.commit()
            return self._analysis_response(case, run, cached=False)
        except Exception as exc:
            self.db.rollback()
            case = self.repository.get_case(case.case_id) or case
            run = self.repository.get_agent_run(run_id) or run
            run.status = "FAILED"
            run.error_code = f"TASK25C_{type(exc).__name__.upper()}"
            run.error_message = "Multimodal analysis failed; retry is allowed."
            run.finished_at = datetime.now(timezone.utc)
            self.repository.save_agent_run(run)
            case.last_error_code = run.error_code
            case.last_error_message = run.error_message
            self.repository.save_case(case)
            if case.status != "FAILED" and "FAILED" in self.state.TRANSITIONS.get(case.status, set()):
                self.state.transition(case, "FAILED", user, reason="analysis_failed", detail={"error_code": run.error_code})
            self.db.commit()
            if isinstance(exc, (MultimodalCaseError, MultimodalCasePermissionError, MultimodalCaseOrchestratorError)):
                raise
            raise MultimodalCaseOrchestratorError(f"Multimodal analysis failed: {type(exc).__name__}") from exc

    def retrieve(self, case: MultimodalMaintenanceCase, payload: MultimodalRetrieveRequest, user: User) -> dict:
        self._require_editor(user)
        evidence = self.repository.list_evidence(case.case_id)
        resolution = MultimodalEntityResolutionService().resolve(
            case, evidence, bound_device=self.repository.get_device(case.device_id) if case.device_id else None
        )
        plan = CrossModalRetrievalPlanService().build(
            original_query=case.user_query or case.normalized_query or case.title,
            normalized_query=case.normalized_query,
            confirmed_facts=case.user_confirmed_facts or {},
            resolution=resolution,
            evidence_items=evidence,
            occurrence_conditions=case.occurrence_conditions or [],
            requested_information=payload.requested_information,
        )
        result = CrossModalRetrievalService(self.db, current_user=user).retrieve(plan, top_k=payload.top_k)
        qa_query = "；".join(item.query for item in plan.queries if item.query).strip()[:2000]
        request_material = json.dumps({
            "case_id": case.case_id,
            "queries": [item.query for item in plan.queries],
            "confirmed_facts": case.user_confirmed_facts or {},
        }, ensure_ascii=False, sort_keys=True)
        qa_request_id = payload.request_id or f"task28a-mm-{hashlib.sha256(request_material.encode('utf-8')).hexdigest()[:40]}"
        qa_response = QueryAwareRetrievalService(self.db, current_user=user).search(QueryAwareSearchRequest(
            query=qa_query or case.user_query or case.title,
            request_id=qa_request_id,
            device_context={
                "device_id": str(case.device_id) if case.device_id else None,
                "device_model": case.device_model,
                "product_family": case.product_family,
                "equipment_category": case.equipment_category,
            },
            retrieval_mode="fast",
            top_k=payload.top_k,
            enable_llm=False,
            allow_real_api=False,
            persist_result=payload.persist_result,
        ))
        case.knowledge_citations = result.citations
        metadata = dict(case.metadata_json or {})
        metadata["cross_modal_retrieval"] = {
            "generated_queries": result.generated_queries,
            "requested_channels": result.requested_channels,
            "actual_channels": result.actual_channels,
            "surface_count": len(result.surfaced_results),
            "citation_validity_ratio": result.citation_validity_ratio,
            "citation_coverage_ratio": result.citation_coverage_ratio,
            "confidence_status": result.confidence_status,
            "stage_latency": result.stage_latency,
            "dedicated_rerank": result.dedicated_rerank,
            "external_call_counts": result.external_call_counts,
            "qa_request_id": qa_response.request_id,
            "qa_record_id": qa_response.qa_record_id,
            "trace_id": qa_response.trace_id,
            "persistence_status": qa_response.persistence_status,
        }
        case.metadata_json = metadata
        if qa_response.trace_id:
            self.media.link_to_qa(
                self.repository.get_media_items(self._case_media_ids(case)),
                qa_response.trace_id,
            )
        for citation in result.citations:
            source_hash = hashlib.sha256(
                f"{citation['document_id']}:{citation['chunk_id']}".encode("utf-8")
            ).hexdigest()
            self.state.add_evidence(case, MultimodalEvidenceCreate(
                modality="KNOWLEDGE_TEXT",
                evidence_type="GENERAL_OBSERVATION",
                source_type="OFFICIAL_KNOWLEDGE",
                source_hash=source_hash,
                observed_text=citation.get("quote"),
                normalized_text=citation.get("quote"),
                page_or_frame_locator=citation.get("source_locator") or {},
                confidence=0.99,
                observation_status="OBSERVED",
                metadata_json={
                    "citation_id": citation.get("citation_id"),
                    "document_id": citation.get("document_id"),
                    "chunk_id": citation.get("chunk_id"),
                    "document_title": citation.get("document_title"),
                    "official_source": True,
                },
            ), user)
        self.repository.save_case(case)
        if result.citations and case.status in {"ANALYZING", "NEEDS_CLARIFICATION", "MEDIA_UPLOADED"}:
            self.state.transition(case, "EVIDENCE_READY", user, reason="cross_modal_retrieval_grounded")
        elif not result.citations and case.status in {"ANALYZING", "EVIDENCE_READY"}:
            self.state.transition(case, "INSUFFICIENT_EVIDENCE", user, reason="cross_modal_retrieval_no_answer")
        self.state.audit(case, user, "cross_modal_retrieval_completed", detail={
            "citation_count": len(result.citations),
            "qa_record_id": qa_response.qa_record_id,
            "trace_id": qa_response.trace_id,
            "qa_persistence_status": qa_response.persistence_status,
            "dedicated_rerank": "DEFERRED_QWEN3_RERANK_CONFIG",
            "external_calls": result.external_call_counts,
        })
        self.db.commit()
        response = result.as_dict()
        response.update({
            "answer": qa_response.answer,
            "references": qa_response.references,
            "suggested_steps": qa_response.suggested_steps,
            "safety_notes": qa_response.safety_notes,
            "trace_id": qa_response.trace_id,
            "qa_record_id": qa_response.qa_record_id,
            "persistence_status": qa_response.persistence_status,
        })
        return response

    def diagnose(self, case: MultimodalMaintenanceCase, payload: MultimodalDiagnoseRequest, user: User) -> dict:
        self._require_editor(user)
        if case.status not in {"EVIDENCE_READY", "DIAGNOSIS_READY", "MULTIPLE_POSSIBILITIES"}:
            raise MultimodalCaseOrchestratorError("Diagnosis requires evidence-ready case state")
        evidence = self.repository.list_evidence(case.case_id)
        conflicts = [item for item in self.repository.list_conflicts(case.case_id) if item.resolution_status == "OPEN"]
        resolution = MultimodalEntityResolutionService().resolve(
            case, evidence, bound_device=self.repository.get_device(case.device_id) if case.device_id else None
        )
        fusion = MultimodalEvidenceFusionService().fuse(evidence)
        safety_citations = [item for item in (case.knowledge_citations or []) if self._is_safety_citation(item)]
        safety = MultimodalSafetyGuardService().evaluate(
            evidence_items=evidence,
            proposed_actions=payload.proposed_actions,
            valid_safety_citations=safety_citations,
            device_state_confirmed_safe=self._safe_state_confirmed(case),
        )
        diagnosis = MultimodalDiagnosisService().build(
            case_id=case.case_id,
            resolution=resolution,
            fusion=fusion,
            citations=case.knowledge_citations or [],
            safety=safety,
            open_conflict_evidence_ids=[eid for item in conflicts for eid in item.evidence_ids],
        )
        persisted = []
        for draft in diagnosis.possible_faults:
            existing = self.repository.get_hypothesis(draft.hypothesis_id)
            if existing:
                persisted.append(existing)
                continue
            saved = self.repository.create_hypothesis(MultimodalDiagnosticHypothesis(
                case_id=case.case_id,
                created_by=user.id,
                **asdict_without_none(draft),
            ))
            persisted.append(saved)
        confidence = MultimodalConfidenceService().calculate(
            fusion,
            valid_citation_count=len(diagnosis.citations),
            open_high_conflicts=sum(item.severity == "HIGH" for item in conflicts),
            required_missing_count=len(diagnosis.missing_information),
        )
        case.safety_level = safety.safety_level
        case.confidence_status = confidence.status
        case.diagnosis_status = diagnosis.confidence_status
        case.missing_information = diagnosis.missing_information
        metadata = dict(case.metadata_json or {})
        metadata["latest_diagnosis"] = {
            "hypothesis_ids": [item.hypothesis_id for item in persisted],
            "unsupported_diagnosis_count": diagnosis.unsupported_diagnosis_count,
            "safety": safety.as_dict(),
            "confidence": asdict_without_none(confidence),
        }
        case.metadata_json = metadata
        self.repository.save_case(case)
        target = "INSUFFICIENT_EVIDENCE" if not persisted else (
            "MULTIPLE_POSSIBILITIES" if len(persisted) > 1 or conflicts else "DIAGNOSIS_READY"
        )
        self.state.transition(case, target, user, reason="diagnosis_completed", detail={
            "hypothesis_count": len(persisted),
            "unsafe_instruction_count": len(safety.blocked_actions),
        })
        self.db.commit()
        output = diagnosis.as_dict()
        output.update({
            "safety": safety.as_dict(),
            "confidence": asdict_without_none(confidence),
            "case_status": case.status,
        })
        return output

    def create_sop_draft(self, case: MultimodalMaintenanceCase, payload: MultimodalSopDraftRequest, user: User) -> dict:
        self._require_editor(user)
        hypotheses = self.repository.list_hypotheses(case.case_id)
        evidence_items = self.repository.list_evidence(case.case_id)
        conflicts = [item for item in self.repository.list_conflicts(case.case_id) if item.resolution_status == "OPEN" and item.severity == "HIGH"]
        user_confirmed_device = any(
            isinstance(item, dict) and item.get("evidence_type") == "DEVICE_MODEL"
            for item in (case.user_confirmed_facts or {}).values()
        ) or any(
            item.evidence_type in {"DEVICE_MODEL", "NAMEPLATE"}
            and item.observation_status == "USER_CONFIRMED"
            and item.user_confirmed
            and bool(item.device_model_candidates or item.normalized_text or item.observed_text)
            for item in evidence_items
        )
        safety_complete = bool(hypotheses) and all(item.safety_warnings for item in hypotheses)
        confidence = max((float(item.confidence) for item in hypotheses), default=0.0)
        decision = MultimodalSopTaskBoundaryService().allow_sop_draft(
            device_model=case.device_model,
            user_confirmed_device=user_confirmed_device,
            valid_citation_count=len(case.knowledge_citations or []),
            safety_complete=safety_complete,
            evidence_confidence=confidence,
            open_high_conflicts=len(conflicts),
        )
        if not decision.allowed:
            return {"case_id": case.case_id, "boundary": decision.as_dict(), "artifact": None}
        existing = self.repository.get_artifact_by_source(case.case_id, "sop_draft")
        if existing:
            return {"case_id": case.case_id, "boundary": decision.as_dict(), "artifact": self._artifact_payload(existing), "cached": True}
        run_id = f"mm-sop-{hashlib.sha256(case.case_id.encode()).hexdigest()[:24]}"
        run = self._ensure_draft_run(run_id, "task25c_multimodal_sop_draft", case, user)
        content = {
            "case_id": case.case_id,
            "status": "DRAFT",
            "applicable_device": case.device_model,
            "fault_symptoms": case.reported_symptoms,
            "prerequisites": ["由具备资质的人员确认设备状态并遵循现场安全制度。"],
            "tools_and_spares": [],
            "safety_requirements": list(dict.fromkeys(warning for item in hypotheses for warning in (item.safety_warnings or []))),
            "ordered_steps": list(dict.fromkeys(check for item in hypotheses for check in (item.recommended_checks or []))),
            "completion_verification": ["依据引用手册和现场记录复核告警状态，不自动宣告修复完成。"],
            "abort_conditions": ["证据冲突、设备状态不明或出现高风险迹象时立即停止。"],
            "citations": case.knowledge_citations,
            "evidence_ids": list(dict.fromkeys(eid for item in hypotheses for eid in (item.supporting_evidence_ids or []))),
            "requires_human_approval": True,
            "automatic_approval": False,
        }
        artifact = self.repository.create_artifact(AgentArtifact(
            run_id=run.run_id,
            artifact_type="sop_draft",
            title=payload.title or f"{case.title} SOP 草稿",
            content_text="该内容为待人工审核的 SOP 草稿，不得直接执行。",
            content_json=content,
            source_type="multimodal_case",
            source_id=case.case_id,
        ))
        self.repository.create_approval(AgentApproval(
            run_id=run.run_id,
            approval_type="sop_approval",
            requested_action="review_sop_draft",
            payload_json={"artifact_id": str(artifact.id), "case_id": case.case_id, "automatic": False},
            status="pending",
            requested_by=user.id,
        ))
        case.sop_draft_id = artifact.id
        self.repository.save_case(case)
        self.state.transition(case, "SOP_DRAFT_READY", user, reason="sop_draft_created", detail={"artifact_id": str(artifact.id)})
        self.db.commit()
        return {"case_id": case.case_id, "boundary": decision.as_dict(), "artifact": self._artifact_payload(artifact), "cached": False}

    def create_task_draft(self, case: MultimodalMaintenanceCase, payload: MultimodalTaskDraftRequest, user: User) -> dict:
        self._require_editor(user)
        if not case.sop_draft_id:
            raise MultimodalCaseOrchestratorError("Task draft requires an SOP draft")
        sop = self.repository.get_artifact(case.sop_draft_id)
        if not sop or sop.artifact_type != "sop_draft":
            raise MultimodalCaseOrchestratorError("SOP draft artifact not found")
        approved = self.repository.get_approved_sop_approval(sop.run_id) is not None
        safety_complete = bool((sop.content_json or {}).get("safety_requirements"))
        decision = MultimodalSopTaskBoundaryService().allow_task_draft(
            sop_status="approved" if approved else "draft",
            sop_user_confirmed=payload.sop_user_confirmed,
            safety_complete=safety_complete,
            role=user.role,
        )
        if not decision.allowed:
            return {"case_id": case.case_id, "boundary": decision.as_dict(), "artifact": None}
        existing = self.repository.get_artifact_by_source(case.case_id, "task_draft")
        if existing:
            return {"case_id": case.case_id, "boundary": decision.as_dict(), "artifact": self._artifact_payload(existing), "cached": True}
        run_id = f"mm-task-{hashlib.sha256(case.case_id.encode()).hexdigest()[:24]}"
        run = self._ensure_draft_run(run_id, "task25c_multimodal_task_draft", case, user)
        hypotheses = self.repository.list_hypotheses(case.case_id)
        content = {
            "case_id": case.case_id,
            "device_id": str(case.device_id) if case.device_id else None,
            "diagnosis_summary": [item.fault_name for item in hypotheses],
            "sop_draft_id": str(sop.id),
            "evidence_summary": [item.hypothesis_id for item in hypotheses],
            "safety_requirements": (sop.content_json or {}).get("safety_requirements", []),
            "assigned_role": payload.assigned_role,
            "status": "DRAFT",
            "created_by": str(user.id),
            "formal_task_created": False,
            "automatic_assignment": False,
        }
        artifact = self.repository.create_artifact(AgentArtifact(
            run_id=run.run_id,
            artifact_type="task_draft",
            title=f"{case.title} 检修任务草稿",
            content_text="该内容为任务草稿，未创建正式检修任务。",
            content_json=content,
            source_type="multimodal_case",
            source_id=case.case_id,
        ))
        case.task_draft_id = artifact.id
        self.repository.save_case(case)
        self.state.transition(case, "TASK_DRAFT_READY", user, reason="task_draft_created", detail={"artifact_id": str(artifact.id)})
        self.db.commit()
        return {"case_id": case.case_id, "boundary": decision.as_dict(), "artifact": self._artifact_payload(artifact), "cached": False}

    def audit(self, case: MultimodalMaintenanceCase) -> list[dict]:
        return [{
            "id": str(item.id),
            "action": item.action,
            "operator": item.operator,
            "trace_id": item.trace_id,
            "detail": item.detail,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        } for item in self.repository.list_audit(case.case_id)]

    def _preprocess_media(self, case: MultimodalMaintenanceCase, media: UploadedMedia, user: User) -> dict:
        source_path = self.media.resolve_file_path(media)
        source_hash = str((media.metadata_json or {}).get("source_sha256") or self._sha256_file(source_path))
        result = ImagePreprocessingService().process(
            media_id=media.id,
            source_path=source_path,
            source_sha256=source_hash,
        )
        summary = {
            "media_id": str(media.id),
            "source_sha256": result.source_sha256,
            "original_width": result.original_width,
            "original_height": result.original_height,
            "normalized_width": result.normalized_width,
            "normalized_height": result.normalized_height,
            "orientation": result.orientation,
            "brightness_mean": result.brightness_mean,
            "contrast_stddev": result.contrast_stddev,
            "edge_variance": result.edge_variance,
            "quality_flags": result.quality_flags,
            "ocr_ready": result.ocr_ready,
            "vision_ready": result.vision_ready,
            "exif_removed": result.exif_removed,
            "variant_hashes": {item.variant_id: item.sha256 for item in result.variants},
        }
        metadata = dict(media.metadata_json or {})
        metadata["task25c_preprocessing"] = summary
        media.metadata_json = metadata
        self.db.add(media)
        evidence_hash = hashlib.sha256(f"{source_hash}:file_metadata".encode()).hexdigest()
        self.state.add_evidence(case, MultimodalEvidenceCreate(
            media_id=media.id,
            modality="FILE_METADATA",
            evidence_type="GENERAL_OBSERVATION",
            source_type="FILE_METADATA",
            source_hash=evidence_hash,
            observed_text="; ".join(result.quality_flags) if result.quality_flags else "image_quality_acceptable",
            normalized_text="; ".join(result.quality_flags) if result.quality_flags else "image_quality_acceptable",
            page_or_frame_locator={"media_id": str(media.id), "locator_type": "whole_image_metadata"},
            confidence=0.99,
            observation_status="OBSERVED",
            metadata_json=summary,
        ), user)
        return summary

    def _ingest_existing_media_evidence(self, case: MultimodalMaintenanceCase, media: UploadedMedia, user: User) -> None:
        ocr = self.repository.latest_ocr_result(media.id)
        if ocr:
            payload = {
                "text": ocr.text or "",
                "confidence": float(ocr.confidence or 0),
                "regions": ocr.regions_json if isinstance(ocr.regions_json, list) else [],
                "provider_trace_id": ocr.external_trace_id,
                **(ocr.raw_result_json or {}),
            }
            for item in OcrEvidenceNormalizationService().to_evidence(
                payload,
                media_id=media.id,
                ocr_result_id=ocr.id,
                provider=ocr.provider_code,
                provider_model=ocr.model_name,
                provider_trace_id=ocr.external_trace_id,
            ):
                self.state.add_evidence(case, item, user)
        elif media.ocr_text:
            ocr_metadata = (media.metadata_json or {}).get("ocr") or {}
            payload = {
                "text": media.ocr_text,
                "confidence": (ocr_metadata.get("metadata") or {}).get("confidence", 0.5),
                "regions": (ocr_metadata.get("metadata") or {}).get("regions", []),
            }
            for item in OcrEvidenceNormalizationService().to_evidence(
                payload,
                media_id=media.id,
                ocr_result_id=None,
                provider=str(ocr_metadata.get("provider") or "legacy_ocr"),
                provider_model=None,
                provider_trace_id=None,
            ):
                self.state.add_evidence(case, item, user)

        analysis = self.repository.latest_ai_analysis(media.id)
        if analysis:
            payload = {
                "observations": analysis.visual_findings_json or ([analysis.summary] if analysis.summary else []),
                "regions": (analysis.raw_response_json or {}).get("regions", []),
                "candidate_device_type": (analysis.detected_device_info_json or {}).get("device_type"),
                "candidate_components": (analysis.raw_response_json or {}).get("candidate_components", []),
                "indicator_states": (analysis.raw_response_json or {}).get("indicator_states", []),
                "visible_damage": (analysis.raw_response_json or {}).get("visible_damage", []),
                "screen_present": (analysis.raw_response_json or {}).get("screen_present", False),
                "nameplate_present": (analysis.raw_response_json or {}).get("nameplate_present", False),
                "needs_ocr": (analysis.raw_response_json or {}).get("needs_ocr", False),
                "image_quality_issue": (analysis.raw_response_json or {}).get("image_quality_issue", []),
                "confidence": float(analysis.confidence or 0),
                "provider": analysis.provider_code,
                "provider_model": analysis.model_name,
                "provider_trace_id": analysis.external_trace_id,
                "diagnosis": analysis.possible_faults_json,
                "recommended_actions": analysis.recommended_actions_json,
                "alarm_codes": analysis.detected_alarm_codes_json,
                "device_model": (analysis.detected_device_info_json or {}).get("model"),
            }
            for item in VisualSignalExtractionService().to_evidence(payload, media_id=media.id, analysis_id=analysis.id):
                self.state.add_evidence(case, item, user)

    def _run_real_provider_jobs(self, media: UploadedMedia, run_id: str, user: User) -> list[str]:
        service = MultimodalEvidenceService(self.db)
        jobs = []
        for job_type, capability in (("ocr", "ocr"), ("multimodal_analysis", "fault_scene_analysis")):
            job = service.create_processing_job(media.id, MediaProcessingJobCreate(
                job_type=job_type,
                capability=capability,
                dry_run=False,
                mock_run=False,
                real_run=True,
                agent_run_id=run_id,
                input_summary={
                    "purpose": "task25c_authorized_case_analysis",
                    "media_id": str(media.id),
                    "source_sha256": (media.metadata_json or {}).get("source_sha256"),
                    "full_image_logged": False,
                },
            ), user)
            jobs.append(str(job.id))
        return jobs

    def _persist_conflicts(self, case, candidates):
        output = []
        for item in candidates:
            existing = self.repository.get_conflict(item.conflict_id)
            if existing:
                output.append(existing)
                continue
            output.append(self.repository.create_conflict(MultimodalEvidenceConflict(
                conflict_id=item.conflict_id,
                case_id=case.case_id,
                conflict_type=item.conflict_type,
                evidence_ids=item.evidence_ids,
                severity=item.severity,
                resolution_required=item.resolution_required,
                recommended_question=item.recommended_question,
                resolution_status=item.resolution_status,
            )))
        return output

    def _apply_resolution(self, case, resolution, questions, preprocessing):
        if resolution.get("resolved_device_model"):
            case.device_model = resolution["resolved_device_model"]
        if resolution.get("resolved_product_family"):
            case.product_family = resolution["resolved_product_family"]
        if resolution.get("resolved_equipment_category"):
            case.equipment_category = resolution["resolved_equipment_category"]
        case.alarm_codes = resolution.get("resolved_alarm_codes", [])
        case.components = resolution.get("resolved_components", [])
        case.missing_information = resolution.get("missing_information", [])
        case.clarifying_questions = questions
        case.confidence_status = "CONFLICTED" if resolution.get("conflicts") else (
            "MEDIUM" if resolution.get("resolution_confidence", 0) >= 0.6 else "INSUFFICIENT_EVIDENCE"
        )
        metadata = dict(case.metadata_json or {})
        metadata["entity_resolution"] = resolution
        metadata["image_preprocessing"] = preprocessing
        metadata["formal_task_created"] = False
        metadata["formal_sop_approved"] = False
        metadata["dedicated_rerank_status"] = "DEFERRED_QWEN3_RERANK_CONFIG"
        case.metadata_json = metadata
        self.repository.save_case(case)

    def _analysis_response(self, case, run, *, cached):
        case = self.repository.get_case(case.case_id) or case
        counts = self.repository.counts(case.case_id)
        return {
            "case_id": case.case_id,
            "job_id": run.run_id,
            "job_status": run.status,
            "case_status": case.status,
            "cached": cached,
            "recoverable": run.status in {"FAILED", "PARTIAL"},
            "evidence_count": counts["evidence_count"],
            "region_count": counts["region_count"],
            "conflict_count": counts["conflict_count"],
            "clarifying_questions": case.clarifying_questions or [],
            "entity_resolution": (case.metadata_json or {}).get("entity_resolution", {}),
            "external_api_called": bool((run.context_json or {}).get("external_api_called")),
            "dedicated_rerank": "DEFERRED_QWEN3_RERANK_CONFIG",
        }

    def _ensure_draft_run(self, run_id, agent_code, case, user):
        existing = self.repository.get_agent_run(run_id)
        if existing:
            return existing
        now = datetime.now(timezone.utc)
        return self.repository.create_agent_run(AgentRun(
            run_id=run_id,
            agent_code=agent_code,
            user_id=user.id,
            device_id=case.device_id,
            status="SUCCEEDED",
            input_media_ids_json=list(case.media_ids or []),
            context_json={"case_id": case.case_id, "automatic_approval": False, "formal_task_created": False},
            provider="deterministic_task25c",
            requires_human_approval=True,
            approval_status="pending",
            started_at=now,
            finished_at=now,
        ))

    @staticmethod
    def _public_media(media):
        preprocessing = (media.metadata_json or {}).get("task25c_preprocessing") or {}
        return {
            "media_id": str(media.id),
            "media_type": media.media_type,
            "original_file_name": media.original_file_name,
            "mime_type": media.mime_type,
            "file_size": media.file_size,
            "status": media.status,
            "preview_url": f"/api/media/{media.id}/content",
            "ocr_status": (media.metadata_json or {}).get("ocr_status"),
            "quality_flags": preprocessing.get("quality_flags", []),
            "ocr_ready": preprocessing.get("ocr_ready"),
            "vision_ready": preprocessing.get("vision_ready"),
            "created_at": media.created_at.isoformat() if media.created_at else None,
        }

    @staticmethod
    def _artifact_payload(item):
        return {
            "artifact_id": str(item.id),
            "artifact_type": item.artifact_type,
            "title": item.title,
            "content_text": item.content_text,
            "content": item.content_json or {},
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    @staticmethod
    def _is_safety_citation(item):
        text = " ".join(str(item.get(key) or "") for key in ("document_title", "section_title", "quote"))
        return any(term in text for term in ("安全", "危险", "断电", "残余电压", "防护", "高压"))

    @staticmethod
    def _safe_state_confirmed(case):
        values = [str(item.get("value") or "") for item in (case.user_confirmed_facts or {}).values() if isinstance(item, dict)]
        return any(term in " ".join(values) for term in ("已断电", "已隔离", "残余电压已确认", "安全状态已确认"))

    @staticmethod
    def _sha256_file(path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _case_media_ids(case):
        output = []
        for value in case.media_ids or []:
            try:
                output.append(UUID(str(value)))
            except (TypeError, ValueError):
                continue
        return output

    @staticmethod
    def _analysis_run_id(case, payload):
        seed = json.dumps({
            "case_id": case.case_id,
            "media_ids": sorted(case.media_ids or []),
            "allow_real_api": payload.allow_real_api,
            "mock_run": payload.mock_run,
            "version": "task25c_analysis_v1",
        }, sort_keys=True)
        suffix = uuid4().hex[:8] if payload.force else hashlib.sha256(seed.encode()).hexdigest()[:24]
        return f"mm-analysis-{suffix}"

    def _require_real_provider_authorization(self, user):
        if not self.settings.TASK25C_ALLOW_REAL_API:
            raise MultimodalCaseOrchestratorError("Real provider calls require TASK25C_ALLOW_REAL_API=true")
        if user.role not in {"admin", "expert"}:
            raise MultimodalCasePermissionError("Real provider calls require expert or admin role")

    @staticmethod
    def _require_editor(user):
        if user.role not in {"admin", "expert", "engineer"}:
            raise MultimodalCasePermissionError("viewer has read-only multimodal access")


def asdict_without_none(value) -> dict:
    from dataclasses import asdict, is_dataclass

    if is_dataclass(value):
        return {key: item for key, item in asdict(value).items() if item is not None}
    if hasattr(value, "__dict__"):
        return {key: item for key, item in value.__dict__.items() if item is not None}
    raise TypeError("value is not serializable")
