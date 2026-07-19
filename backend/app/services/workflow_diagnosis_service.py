from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import DiagnosisRecord, User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.maintenance_workflow import DiagnosisDraftRequest
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService


class WorkflowDiagnosisService:
    OPERATION = "CREATE_DIAGNOSIS_DRAFT"

    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()

    def create_draft(self, workflow_id: str, payload: DiagnosisDraftRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.diagnosis_id:
            result = self.workflows.to_detail(workflow, user)
            result["idempotent_replay"] = True
            result["reused_diagnosis"] = True
            return result

        case = self.repository.get_case(workflow.case_id)
        if not case:
            raise MaintenanceWorkflowError("workflow case not found")
        evidence = self.repository.list_evidence(case.case_id)
        hypotheses = self.repository.list_hypotheses(case.case_id)
        conflicts = self.repository.list_open_high_conflicts(case.case_id)
        citations = [item for item in (case.knowledge_citations or []) if self._valid_citation(item)]
        has_input = bool(case.user_query or case.media_ids or evidence)
        locators_valid = bool(evidence) and all(
            bool(item.source_hash)
            and (item.modality == "USER_TEXT" or bool(item.page_or_frame_locator) or bool(item.media_id))
            for item in evidence
            if item.source_type != "OFFICIAL_KNOWLEDGE"
        )
        decision = self.policy.can_create_diagnosis(
            case_status=case.status,
            has_input_evidence=has_input,
            evidence_has_locator=locators_valid,
            citation_count=len(citations),
            open_high_conflicts=len(conflicts),
            hypothesis_count=len(hypotheses),
        )
        before = self.workflows.workflow_snapshot(workflow)
        if not decision.allowed:
            workflow.status = "WAITING_USER" if case.status == "NEEDS_CLARIFICATION" else "BLOCKED"
            workflow.blocking_reason = "; ".join(decision.reasons)
            workflow.required_action = decision.required_action
            workflow.lock_version += 1
            self.repository.save_workflow(workflow)
            result = {
                "workflow": self.workflows.workflow_snapshot(workflow),
                "diagnosis": None,
                "policy": decision.as_dict(),
            }
            self.workflows.record_event(
                workflow,
                user,
                event_type="DIAGNOSIS_BLOCKED",
                operation=self.OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=workflow.blocking_reason,
                result=result,
            )
            self.db.commit()
            return result

        if workflow.current_stage == "CASE_ANALYSIS":
            intermediate_before = self.workflows.workflow_snapshot(workflow)
            self.workflows.transition_stage(
                workflow,
                "EVIDENCE_REVIEW",
                status="ACTIVE",
                required_action="validate diagnosis draft",
            )
            self.workflows.record_event(
                workflow,
                user,
                event_type="EVIDENCE_ANALYZED",
                operation="DIAGNOSIS_DRAFT_PRECHECK",
                idempotency_key=None,
                before=intermediate_before,
                after=self.workflows.workflow_snapshot(workflow),
                reason="case evidence and citations validated",
                result={"validated": True},
            )
        if workflow.current_stage != "EVIDENCE_REVIEW":
            raise MaintenanceWorkflowError("diagnosis draft is only allowed during evidence review")

        device = self.repository.get_device(workflow.device_id)
        version = workflow.diagnosis_version + 1
        trace_id = f"wfdiag-{hashlib.sha256(f'{workflow.workflow_id}:{version}'.encode()).hexdigest()[:48]}"
        possible_causes = [item.fault_name for item in hypotheses]
        inspection_steps = list(dict.fromkeys(
            step for item in hypotheses for step in (item.recommended_checks or []) if step
        ))
        safety_notes = list(dict.fromkeys(
            note for item in hypotheses for note in (item.safety_warnings or []) if note
        ))
        recommended_actions = list(inspection_steps)
        diagnosis = DiagnosisRecord(
            manufacturer=getattr(device, "manufacturer", None),
            product_series=getattr(device, "product_series", None) or case.product_family,
            device_id=workflow.device_id,
            device_type=getattr(device, "device_type", None) or case.equipment_category or "unknown",
            device_name=getattr(device, "device_name", None),
            model=getattr(device, "model", None) or case.device_model,
            fault_type=hypotheses[0].fault_category if hypotheses else "unknown",
            alarm_code=(case.alarm_codes or [None])[0],
            alarm_info=None,
            fault_description=case.user_query or case.title,
            device_status=None,
            possible_causes=possible_causes,
            inspection_steps=inspection_steps,
            safety_notes=safety_notes,
            recommended_actions=recommended_actions,
            references=citations,
            related_history=[],
            media_ids=list(case.media_ids or []),
            model_provider="deterministic_workflow",
            model_name="task25d_workflow_diagnosis_v1",
            confidence=max((float(item.confidence) for item in hypotheses), default=0.0),
            trace_id=trace_id,
            created_by=user.id,
        )
        try:
            diagnosis = self.repository.create_diagnosis(diagnosis)
            snapshot = {
                "status": "EVIDENCE_SUPPORTED",
                "version": version,
                "observed_facts": [
                    item.observed_text or item.normalized_text
                    for item in evidence
                    if item.observation_status in {"OBSERVED", "USER_CONFIRMED"}
                    and (item.observed_text or item.normalized_text)
                ],
                "user_confirmed_facts": case.user_confirmed_facts or {},
                "inferred_observations": [
                    item.normalized_text or item.observed_text
                    for item in evidence
                    if item.observation_status in {"INFERRED", "LOW_CONFIDENCE"}
                    and (item.normalized_text or item.observed_text)
                ],
                "possible_faults": [
                    {
                        "hypothesis_id": item.hypothesis_id,
                        "fault_category": item.fault_category,
                        "fault_name": item.fault_name,
                        "confidence": float(item.confidence),
                        "supporting_evidence_ids": item.supporting_evidence_ids,
                        "contradicting_evidence_ids": item.contradicting_evidence_ids,
                    }
                    for item in hypotheses
                ],
                "supporting_evidence": list(dict.fromkeys(
                    evidence_id for item in hypotheses for evidence_id in (item.supporting_evidence_ids or [])
                )),
                "contradicting_evidence": list(dict.fromkeys(
                    evidence_id for item in hypotheses for evidence_id in (item.contradicting_evidence_ids or [])
                )),
                "missing_information": list(dict.fromkeys(
                    missing for item in hypotheses for missing in (item.missing_information or [])
                )),
                "recommended_checks": inspection_steps,
                "safety_warnings": safety_notes,
                "citations": citations,
                "confidence_status": case.confidence_status,
                "confirmation_history": [],
                "generated_as": "DRAFT",
                "validated_by": "deterministic_source_gate",
            }
            workflow.diagnosis_id = diagnosis.id
            workflow.diagnosis_version = version
            workflow.diagnosis_snapshot = snapshot
            workflow.diagnosis_status = "EVIDENCE_SUPPORTED"
            self.workflows.transition_stage(
                workflow,
                "DIAGNOSIS_REVIEW",
                status="WAITING_ENGINEER",
                required_action="confirm, reject, or request reanalysis",
            )
            result = {
                "workflow": self.workflows.workflow_snapshot(workflow),
                "diagnosis": self.workflows.diagnosis_payload(diagnosis),
                "diagnosis_snapshot": snapshot,
                "policy": decision.as_dict(),
                "automatic_confirmation": False,
            }
            self.workflows.record_event(
                workflow,
                user,
                event_type="DIAGNOSIS_DRAFTED",
                operation=self.OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.reason or "evidence-supported diagnosis draft created",
                result=result,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, self.OPERATION, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError("diagnosis draft concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"diagnosis draft write failed: {exc.__class__.__name__}") from exc

    @staticmethod
    def _valid_citation(item: dict) -> bool:
        return bool(
            isinstance(item, dict)
            and item.get("document_id")
            and item.get("chunk_id")
            and (item.get("source_locator") or item.get("page_number") is not None or item.get("section_title"))
        )
