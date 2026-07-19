from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.maintenance_record_repository import MaintenanceRecordRepository
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.maintenance_task import MaintenanceTaskCompleteRequest
from app.schemas.maintenance_workflow import WorkflowTaskCompleteRequest, WorkflowTaskVerificationRequest
from app.services.maintenance_feedback_loop_service import MaintenanceFeedbackLoopService
from app.services.maintenance_record_service import MaintenanceRecordService, MaintenanceRecordServiceError
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService
from app.services.task_execution_record_service import TaskExecutionRecordService


class TaskCompletionVerificationService:
    VERIFY_OPERATION = "VERIFY_TASK_COMPLETION"
    COMPLETE_OPERATION = "COMPLETE_TASK"

    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()
        self.execution = TaskExecutionRecordService(db)
        self.record_service = MaintenanceRecordService(MaintenanceRecordRepository(db))

    def verify(self, workflow_id: str, payload: WorkflowTaskVerificationRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.VERIFY_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "TASK_EXECUTION":
            raise MaintenanceWorkflowError("completion verification requires task execution stage")
        task = self.repository.get_task(workflow.formal_task_id, lock=True)
        if not task or task.status != "in_progress":
            raise MaintenanceWorkflowError("task must be in progress before verification")
        if user.role == "engineer" and task.assignee_id != user.id:
            raise MaintenanceWorkflowError("engineer is not the assigned task executor")
        steps = self.repository.list_steps(workflow.workflow_id)
        records = self.repository.list_execution_records(workflow.workflow_id)
        required_steps_complete = all(
            item.status == "COMPLETED" for item in steps if item.is_required
        )
        safety_steps_complete = all(
            item.status == "COMPLETED" for item in steps if item.is_safety_step
        )
        verification_steps = [item for item in steps if (item.metadata_json or {}).get("verification_required")]
        verification_steps_complete = bool(verification_steps) and all(
            item.status == "COMPLETED" and item.verification_status == "PASSED"
            for item in verification_steps
        )
        unresolved_safety_events = self._unresolved_safety_events(records)
        has_measurements = any(item.measurements for item in records)
        has_media = any(item.media_ids for item in records)
        decision = self.policy.can_verify_completion(
            required_steps_complete=required_steps_complete,
            safety_steps_complete=safety_steps_complete,
            verification_steps_complete=verification_steps_complete,
            unresolved_safety_events=unresolved_safety_events,
            required_measurements_present=payload.required_measurements_present and has_measurements,
            required_media_present=payload.required_media_present and has_media,
        )
        if payload.outcome in {"VERIFIED_SUCCESS", "VERIFIED_PARTIAL"} and not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))
        before = self.workflows.workflow_snapshot(workflow)
        record = self.execution._create_record(
            workflow,
            task,
            user,
            record_type="VERIFICATION",
            content=payload.verification_summary,
            safety_state="NORMAL" if unresolved_safety_events == 0 else "BLOCKED",
            result={
                "outcome": payload.outcome,
                "accepted_partial": payload.accepted_partial,
                "required_steps_complete": required_steps_complete,
                "safety_steps_complete": safety_steps_complete,
                "verification_steps_complete": verification_steps_complete,
                "unresolved_safety_events": unresolved_safety_events,
                "required_measurements_present": payload.required_measurements_present and has_measurements,
                "required_media_present": payload.required_media_present and has_media,
                "policy": decision.as_dict(),
            },
        )
        self.workflows.transition_stage(
            workflow,
            "RESULT_VERIFICATION",
            status="WAITING_ENGINEER",
            blocking_reason=None if payload.outcome in {"VERIFIED_SUCCESS", "VERIFIED_PARTIAL"} else payload.verification_summary,
            required_action="confirm task completion" if payload.outcome in {"VERIFIED_SUCCESS", "VERIFIED_PARTIAL"} else "resume task and perform rework",
        )
        if payload.outcome in {"VERIFICATION_FAILED", "NEEDS_REWORK"}:
            task.status = task.task_status = "paused"
            self.repository.save_task(task)
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "verification": self.workflows.execution_record_payload(record),
            "policy": decision.as_dict(),
            "completion_allowed": payload.outcome in {"VERIFIED_SUCCESS", "VERIFIED_PARTIAL"} and decision.allowed,
        }
        self.workflows.record_event(
            workflow,
            user,
            event_type="VERIFICATION_SUBMITTED",
            operation=self.VERIFY_OPERATION,
            idempotency_key=payload.idempotency_key,
            before=before,
            after=self.workflows.workflow_snapshot(workflow),
            reason=payload.verification_summary,
            result=result,
            task_id=task.id,
        )
        self.db.commit()
        return result

    def complete(self, workflow_id: str, payload: WorkflowTaskCompleteRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.COMPLETE_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "RESULT_VERIFICATION":
            raise MaintenanceWorkflowError("task completion requires verified result stage")
        task = self.repository.get_task(workflow.formal_task_id, lock=True)
        case = self.repository.get_case(workflow.case_id)
        device = self.repository.get_device(workflow.device_id)
        if not task or not case or not device:
            raise MaintenanceWorkflowError("task, case, or device context is missing")
        if user.role == "engineer" and task.assignee_id != user.id:
            raise MaintenanceWorkflowError("engineer is not the assigned task reviewer")
        if case.safety_level in {"HIGH", "CRITICAL", "STOP_WORK"} and user.role not in {"expert", "admin"}:
            raise MaintenanceWorkflowError("high-risk task result requires expert or admin review")
        records = self.repository.list_execution_records(workflow.workflow_id)
        verifications = [item for item in records if item.record_type == "VERIFICATION"]
        if not verifications:
            raise MaintenanceWorkflowError("verification record is required")
        latest_verification = verifications[-1]
        outcome = (latest_verification.result or {}).get("outcome")
        accepted_partial = bool((latest_verification.result or {}).get("accepted_partial"))
        if outcome not in {"VERIFIED_SUCCESS", "VERIFIED_PARTIAL"}:
            raise MaintenanceWorkflowError("failed verification cannot complete task")
        if outcome == "VERIFIED_PARTIAL" and not accepted_partial:
            raise MaintenanceWorkflowError("partial verification was not accepted")
        if self._unresolved_safety_events(records):
            raise MaintenanceWorkflowError("unresolved safety event blocks task completion")
        before = self.workflows.workflow_snapshot(workflow)
        media_ids = list(dict.fromkeys(
            UUID(value) for item in records for value in (item.media_ids or []) if self._is_uuid(value)
        ))
        parts = list(dict.fromkeys([
            *payload.replaced_parts,
            *(part for item in records for part in (item.parts_replaced or [])),
        ]))
        completion_request = MaintenanceTaskCompleteRequest(
            root_cause=payload.actual_fault_cause,
            repair_action="；".join(payload.actual_actions),
            replaced_parts=parts,
            verification_result=str((latest_verification.result or {}).get("outcome")),
            is_recurrent=False,
            completed_at=datetime.now(timezone.utc),
            maintenance_record_remark=payload.comment,
            media_ids=media_ids,
        )
        task.status = task.task_status = "completed"
        task.root_cause = payload.actual_fault_cause
        task.repair_action = "；".join(payload.actual_actions)
        task.replaced_parts = parts
        task.verification_result = outcome
        task.result_summary = payload.comment
        task.completion_notes = payload.comment
        task.completed_by = user.id
        task.completed_at = completion_request.completed_at
        try:
            maintenance_record = self.repository.get_device_record_by_task(task.id)
            if not maintenance_record:
                maintenance_record = self.record_service.ensure_record_from_task(
                    task=task,
                    device=device,
                    payload=completion_request,
                    current_user=user,
                )
            self.repository.save_task(task)
        except MaintenanceRecordServiceError as exc:
            raise MaintenanceWorkflowError(str(exc)) from exc
        sop_execution = self.repository.get_sop_execution(task.sop_execution_id)
        if sop_execution:
            sop_execution.status = "completed"
            sop_execution.started_at = sop_execution.started_at or datetime.now(timezone.utc)
            sop_execution.completed_at = datetime.now(timezone.utc)
            sop_execution.step_results = [self.workflows.step_payload(item) for item in self.repository.list_steps(workflow.workflow_id)]
            self.db.add(sop_execution)
        actual_result = {
            "initial_diagnosis": workflow.diagnosis_snapshot,
            "confirmed_diagnosis": {
                "diagnosis_status": workflow.diagnosis_status,
                "selected_hypothesis_id": (workflow.diagnosis_snapshot or {}).get("selected_hypothesis_id"),
            },
            "actual_fault_cause": payload.actual_fault_cause,
            "actual_actions": payload.actual_actions,
            "replaced_parts": parts,
            "verification_result": outcome,
            "final_device_status": payload.final_device_status,
            "diagnosis_match_status": payload.diagnosis_match_status,
            "new_media_ids": [str(value) for value in media_ids],
            "diagnosis_deviation": payload.diagnosis_match_status in {"MISMATCHED", "PARTIALLY_MATCHED"},
            "knowledge_correction_recommended": payload.diagnosis_match_status in {"MISMATCHED", "PARTIALLY_MATCHED"},
            "completed_by": str(user.id),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        completion_record = self.execution._create_record(
            workflow,
            task,
            user,
            record_type="COMPLETION_REQUEST",
            content=payload.comment,
            media_ids=[str(value) for value in media_ids],
            parts_replaced=parts,
            safety_state="NORMAL",
            result=actual_result,
        )
        workflow.record_id = maintenance_record.id
        workflow.actual_result = actual_result
        workflow.diagnosis_match_status = payload.diagnosis_match_status
        case_metadata = dict(case.metadata_json or {})
        case_metadata["task25d_execution_result"] = actual_result
        case.metadata_json = case_metadata
        self.db.add(case)
        feedback = MaintenanceFeedbackLoopService.build(
            initial_diagnosis=workflow.diagnosis_snapshot or {},
            actual_result=actual_result,
            execution_records=[self.workflows.execution_record_payload(item) for item in records],
            citations=list((workflow.diagnosis_snapshot or {}).get("citations") or []),
            user_feedback=payload.user_feedback,
        )
        metadata = dict(workflow.metadata_json or {})
        metadata["feedback_loop"] = feedback
        workflow.metadata_json = metadata
        self.workflows.transition_stage(
            workflow,
            "TASK_COMPLETED",
            status="ACTIVE",
            required_action="create correction draft if evidence indicates a knowledge gap, then close workflow",
        )
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "formal_task": self.workflows.task_payload(task),
            "maintenance_record_id": str(maintenance_record.id),
            "completion_record": self.workflows.execution_record_payload(completion_record),
            "actual_result": actual_result,
            "feedback": feedback,
            "automatic_completion": False,
        }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type="TASK_COMPLETED",
                operation=self.COMPLETE_OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.comment,
                result=result,
                task_id=task.id,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, self.COMPLETE_OPERATION, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError("task completion concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"task completion failed: {exc.__class__.__name__}") from exc

    @staticmethod
    def _unresolved_safety_events(records) -> int:
        safety = [item for item in records if item.record_type == "SAFETY_EVENT"]
        if not safety:
            return 0
        return 0 if safety[-1].safety_state == "RESOLVED" else 1

    @staticmethod
    def _is_uuid(value) -> bool:
        try:
            UUID(str(value))
        except (TypeError, ValueError):
            return False
        return True
