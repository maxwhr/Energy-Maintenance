from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.maintenance_workflow import DiagnosisConfirmationRequest
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService


class DiagnosisConfirmationService:
    OPERATION = "CONFIRM_DIAGNOSIS"

    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()

    def confirm(self, workflow_id: str, payload: DiagnosisConfirmationRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "DIAGNOSIS_REVIEW" or not workflow.diagnosis_id:
            raise MaintenanceWorkflowError("diagnosis confirmation requires a diagnosis draft under review")
        case = self.repository.get_case(workflow.case_id)
        if not case:
            raise MaintenanceWorkflowError("workflow case not found")
        high_risk = case.safety_level in {"HIGH", "CRITICAL", "STOP_WORK"}
        decision = self.policy.can_confirm_diagnosis(
            action=payload.action,
            actor_role=user.role,
            high_risk=high_risk,
        )
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))

        hypothesis = None
        if payload.selected_hypothesis_id:
            hypothesis = self.repository.get_hypothesis_by_public_id(case.case_id, payload.selected_hypothesis_id)
            if not hypothesis:
                raise MaintenanceWorkflowError("selected diagnosis hypothesis not found")
        before = self.workflows.workflow_snapshot(workflow)
        snapshot = dict(workflow.diagnosis_snapshot or {})
        history = list(snapshot.get("confirmation_history") or [])
        confirmation = {
            "action": payload.action,
            "confirmed_fields": payload.confirmed_fields,
            "rejected_fields": payload.rejected_fields,
            "selected_hypothesis_id": payload.selected_hypothesis_id,
            "comment": payload.comment,
            "actor_id": str(user.id),
            "actor_role": user.role,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
        history.append(confirmation)
        snapshot["confirmation_history"] = history
        snapshot["selected_hypothesis_id"] = payload.selected_hypothesis_id
        snapshot["confirmed_fields"] = {
            **dict(snapshot.get("confirmed_fields") or {}),
            **payload.confirmed_fields,
        }
        snapshot["rejected_fields"] = list(dict.fromkeys([
            *(snapshot.get("rejected_fields") or []),
            *payload.rejected_fields,
        ]))

        if payload.action == "REQUEST_REANALYSIS":
            workflow.diagnosis_status = "DRAFT"
            snapshot["status"] = "DRAFT"
            workflow.diagnosis_snapshot = snapshot
            self.workflows.transition_stage(
                workflow,
                "CASE_ANALYSIS",
                status="ACTIVE",
                required_action="reanalyze case evidence",
            )
            event_type = "DIAGNOSIS_REANALYSIS_REQUESTED"
        elif payload.action == "REJECT":
            workflow.diagnosis_status = "REJECTED"
            snapshot["status"] = "REJECTED"
            workflow.diagnosis_snapshot = snapshot
            workflow.status = "WAITING_ENGINEER"
            workflow.blocking_reason = payload.comment
            workflow.required_action = "request reanalysis or revise evidence"
            workflow.lock_version += 1
            self.repository.save_workflow(workflow)
            if hypothesis:
                hypothesis.status = "CONTRADICTED"
                self.repository.save_hypothesis(hypothesis)
            event_type = "DIAGNOSIS_REJECTED"
        else:
            if payload.action == "USER_CONFIRM":
                target_status = "USER_CONFIRMED"
                hypothesis_status = "USER_CONFIRMED"
                event_type = "DIAGNOSIS_CONFIRMED"
            elif payload.action == "ENGINEER_CONFIRM":
                target_status = "ENGINEER_CONFIRMED"
                hypothesis_status = "ENGINEER_CONFIRMED"
                event_type = "DIAGNOSIS_CONFIRMED"
            else:
                target_status = "ENGINEER_CONFIRMED"
                hypothesis_status = "ENGINEER_CONFIRMED"
                snapshot["expert_reviewed"] = True
                event_type = "DIAGNOSIS_EXPERT_REVIEWED"
            workflow.diagnosis_status = target_status
            snapshot["status"] = target_status
            workflow.diagnosis_snapshot = snapshot
            if hypothesis:
                workflow.diagnosis_hypothesis_id = hypothesis.id
                hypothesis.status = hypothesis_status
                self.repository.save_hypothesis(hypothesis)
            case_facts = dict(case.user_confirmed_facts or {})
            if payload.action == "USER_CONFIRM":
                case_facts.update(payload.confirmed_fields)
                case.user_confirmed_facts = case_facts
                self.db.add(case)
            if high_risk and payload.action != "EXPERT_REVIEW":
                workflow.status = "WAITING_EXPERT"
                workflow.required_action = "expert review high-risk diagnosis"
                workflow.blocking_reason = "high-risk diagnosis requires expert review"
                workflow.lock_version += 1
                self.repository.save_workflow(workflow)
            else:
                self.workflows.transition_stage(
                    workflow,
                    "SOP_DRAFT",
                    status="ACTIVE",
                    required_action="generate SOP draft",
                )

        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "diagnosis_status": workflow.diagnosis_status,
            "confirmation": confirmation,
            "policy": decision.as_dict(),
            "automatic_confirmation": False,
        }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type=event_type,
                operation=self.OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.comment or payload.action,
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
            raise MaintenanceWorkflowError("diagnosis confirmation concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"diagnosis confirmation failed: {exc.__class__.__name__}") from exc
