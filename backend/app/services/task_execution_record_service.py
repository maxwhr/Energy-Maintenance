from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import MaintenanceTaskExecutionRecord, User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.maintenance_workflow import (
    WorkflowTaskActionRequest,
    WorkflowTaskRecordCreate,
    WorkflowTaskStepUpdate,
)
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService
from app.services.media_service import MediaService, MediaServiceError


class TaskExecutionRecordService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()
        self.media = MediaService(db)

    def start(self, workflow_id: str, payload: WorkflowTaskActionRequest, user: User) -> dict:
        return self._task_action(workflow_id, payload, user, action="START")

    def pause(self, workflow_id: str, payload: WorkflowTaskActionRequest, user: User) -> dict:
        return self._task_action(workflow_id, payload, user, action="PAUSE")

    def resume(self, workflow_id: str, payload: WorkflowTaskActionRequest, user: User) -> dict:
        return self._task_action(workflow_id, payload, user, action="RESUME")

    def _task_action(self, workflow_id: str, payload: WorkflowTaskActionRequest, user: User, *, action: str) -> dict:
        operation = f"TASK_{action}"
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        if user.role not in self.policy.TASK_EXECUTION_ROLES:
            raise MaintenanceWorkflowError("task execution role required")
        replay = self.workflows.idempotent_replay(workflow, operation, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        task = self.repository.get_task(workflow.formal_task_id, lock=True)
        if not task:
            raise MaintenanceWorkflowError("formal task not found")
        if user.role == "engineer" and task.assignee_id != user.id:
            raise MaintenanceWorkflowError("engineer must be the explicitly assigned task executor")
        before = self.workflows.workflow_snapshot(workflow)
        current = task.status or task.task_status
        now = datetime.now(timezone.utc)
        if action == "START":
            if workflow.current_stage != "TASK_CREATED" or current not in {"pending", "assigned"}:
                raise MaintenanceWorkflowError("only a created pending task can be started")
            task.status = task.task_status = "in_progress"
            execution = self.repository.get_sop_execution(task.sop_execution_id)
            if execution:
                execution.status = "in_progress"
                execution.started_at = execution.started_at or now
                self.db.add(execution)
            self.workflows.transition_stage(
                workflow,
                "TASK_EXECUTION",
                status="ACTIVE",
                required_action="execute SOP steps and record evidence",
            )
            event_type = "TASK_STARTED"
        elif action == "PAUSE":
            if workflow.current_stage != "TASK_EXECUTION" or current != "in_progress":
                raise MaintenanceWorkflowError("only an in-progress task can be paused")
            task.status = task.task_status = "paused"
            workflow.status = "WAITING_ENGINEER"
            workflow.required_action = "resume task when safe to continue"
            workflow.lock_version += 1
            self.repository.save_workflow(workflow)
            event_type = "TASK_PAUSED"
        else:
            if current != "paused":
                raise MaintenanceWorkflowError("only a paused task can be resumed")
            task.status = task.task_status = "in_progress"
            if workflow.current_stage == "RESULT_VERIFICATION":
                self.workflows.transition_stage(
                    workflow,
                    "TASK_EXECUTION",
                    status="ACTIVE",
                    required_action="perform rework and update evidence",
                )
            else:
                workflow.status = "ACTIVE"
                workflow.blocking_reason = None
                workflow.required_action = "continue task execution"
                workflow.lock_version += 1
                self.repository.save_workflow(workflow)
            event_type = "TASK_RESUMED"
        self.repository.save_task(task)
        record = self._create_record(
            workflow,
            task,
            user,
            record_type=action,
            content=payload.reason or action.lower(),
            safety_state="NORMAL",
            result={"task_status": task.status},
        )
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "formal_task": self.workflows.task_payload(task),
            "execution_record": self.workflows.execution_record_payload(record),
            "automatic_transition": False,
        }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type=event_type,
                operation=operation,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.reason or action,
                result=result,
                task_id=task.id,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, operation, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError(f"task {action.lower()} concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"task {action.lower()} failed: {exc.__class__.__name__}") from exc

    def add_record(self, workflow_id: str, payload: WorkflowTaskRecordCreate, user: User) -> dict:
        operation = "ADD_TASK_RECORD"
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        if user.role not in self.policy.TASK_EXECUTION_ROLES:
            raise MaintenanceWorkflowError("task execution role required")
        replay = self.workflows.idempotent_replay(workflow, operation, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage not in {"TASK_EXECUTION", "RESULT_VERIFICATION"}:
            raise MaintenanceWorkflowError("task records require task execution or verification stage")
        task = self.repository.get_task(workflow.formal_task_id, lock=True)
        if not task or task.status not in {"in_progress", "paused"}:
            raise MaintenanceWorkflowError("task must be in progress or paused")
        if user.role == "engineer" and task.assignee_id != user.id:
            raise MaintenanceWorkflowError("engineer is not the assigned task executor")
        step = None
        if payload.step_id:
            step = self.repository.get_step(workflow.workflow_id, payload.step_id)
            if not step:
                raise MaintenanceWorkflowError("task step not found")
        media_items = []
        if payload.media_ids:
            try:
                media_items = self.media.resolve_media_items(payload.media_ids, device_id=workflow.device_id)
                self.media.link_to_task(media_items, task.id)
            except MediaServiceError as exc:
                raise MaintenanceWorkflowError(str(exc)) from exc
        correction_of = self.repository.get_execution_record(payload.correction_of_id)
        if payload.correction_of_id and (not correction_of or correction_of.workflow_id != workflow.workflow_id):
            raise MaintenanceWorkflowError("corrected execution record not found in workflow")
        before = self.workflows.workflow_snapshot(workflow)
        record = self._create_record(
            workflow,
            task,
            user,
            record_type=payload.record_type,
            content=payload.content,
            media_ids=[str(item.id) for item in media_items],
            measurements=[item.model_dump(mode="json") for item in payload.measurements],
            parts_replaced=payload.parts_replaced,
            safety_state=payload.safety_state,
            result=payload.result,
            step_execution_id=step.id if step else None,
            correction_of_id=correction_of.id if correction_of else None,
            version=(correction_of.version + 1) if correction_of else 1,
        )
        if payload.record_type == "SAFETY_EVENT" and payload.safety_state in {"WARNING", "BLOCKED"}:
            workflow.status = "BLOCKED"
            workflow.blocking_reason = payload.content or "unresolved safety event"
            workflow.required_action = "resolve safety event before continuing"
            workflow.lock_version += 1
            self.repository.save_workflow(workflow)
            event_type = "SAFETY_EVENT"
        elif payload.record_type == "SAFETY_EVENT" and payload.safety_state == "RESOLVED":
            workflow.status = "ACTIVE"
            workflow.blocking_reason = None
            workflow.required_action = "continue task execution"
            workflow.lock_version += 1
            self.repository.save_workflow(workflow)
            event_type = "SAFETY_EVENT_RESOLVED"
        else:
            event_type = "STEP_RECORDED" if payload.step_id else "TASK_RECORD_ADDED"
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "execution_record": self.workflows.execution_record_payload(record),
            "immutable": True,
        }
        self.workflows.record_event(
            workflow,
            user,
            event_type=event_type,
            operation=operation,
            idempotency_key=payload.idempotency_key,
            before=before,
            after=self.workflows.workflow_snapshot(workflow),
            reason=payload.content or payload.record_type,
            result=result,
            task_id=task.id,
        )
        self.db.commit()
        return result

    def update_step(self, workflow_id: str, step_id, payload: WorkflowTaskStepUpdate, user: User) -> dict:
        operation = f"UPDATE_TASK_STEP:{step_id}"
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, operation, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "TASK_EXECUTION" or workflow.status == "BLOCKED":
            raise MaintenanceWorkflowError("task step update requires active task execution")
        task = self.repository.get_task(workflow.formal_task_id, lock=True)
        if not task or task.status != "in_progress":
            raise MaintenanceWorkflowError("task must be in progress")
        if user.role == "engineer" and task.assignee_id != user.id:
            raise MaintenanceWorkflowError("engineer is not the assigned task executor")
        step = self.repository.get_step(workflow.workflow_id, step_id, lock=True)
        if not step:
            raise MaintenanceWorkflowError("task step not found")
        all_steps = self.repository.list_steps(workflow.workflow_id)
        prerequisites_satisfied = self._prerequisites_satisfied(step, all_steps)
        decision = self.policy.can_transition_step(
            current=step.status,
            target=payload.status,
            is_safety_step=step.is_safety_step,
            skip_reason=payload.skip_reason,
            prerequisites_satisfied=prerequisites_satisfied,
        )
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))
        before_step = self.workflows.step_payload(step)
        now = datetime.now(timezone.utc)
        step.status = payload.status
        step.result_summary = payload.result_summary
        step.evidence_ids = list(dict.fromkeys(payload.evidence_ids))
        step.skip_reason = payload.skip_reason
        step.verification_status = payload.verification_status
        step.performed_by = user.id
        if payload.status == "IN_PROGRESS":
            step.started_at = step.started_at or now
        if payload.status in {"COMPLETED", "SKIPPED_WITH_REASON", "FAILED"}:
            step.started_at = step.started_at or now
            step.completed_at = now
        self.repository.save_step(step)
        record = self._create_record(
            workflow,
            task,
            user,
            record_type="STEP_RESULT",
            content=payload.result_summary or payload.skip_reason or payload.status,
            safety_state="NORMAL",
            result={
                "step_id": str(step.id),
                "status": step.status,
                "verification_status": step.verification_status,
                "skip_reason": step.skip_reason,
            },
            step_execution_id=step.id,
        )
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "step": self.workflows.step_payload(step),
            "execution_record": self.workflows.execution_record_payload(record),
            "policy": decision.as_dict(),
        }
        self.workflows.record_event(
            workflow,
            user,
            event_type="STEP_RECORDED",
            operation=operation,
            idempotency_key=payload.idempotency_key,
            before=before_step,
            after=self.workflows.step_payload(step),
            reason=payload.result_summary or payload.skip_reason or payload.status,
            result=result,
            task_id=task.id,
        )
        self.db.commit()
        return result

    def _create_record(
        self,
        workflow,
        task,
        user,
        *,
        record_type: str,
        content: str | None,
        media_ids: list[str] | None = None,
        measurements: list[dict] | None = None,
        parts_replaced: list[str] | None = None,
        safety_state: str,
        result: dict,
        step_execution_id=None,
        correction_of_id=None,
        version: int = 1,
    ) -> MaintenanceTaskExecutionRecord:
        evidence_payload = {
            "workflow_id": workflow.workflow_id,
            "task_id": str(task.id),
            "record_type": record_type,
            "content": content,
            "media_ids": media_ids or [],
            "measurements": measurements or [],
            "parts_replaced": parts_replaced or [],
            "safety_state": safety_state,
            "result": result,
            "performed_by": str(user.id),
            "version": version,
        }
        digest = hashlib.sha256(
            json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return self.repository.create_execution_record(MaintenanceTaskExecutionRecord(
            record_id=f"wfr_{uuid4().hex}",
            workflow_id=workflow.workflow_id,
            task_id=task.id,
            step_execution_id=step_execution_id,
            record_type=record_type,
            content=content,
            media_ids=media_ids or [],
            measurements=measurements or [],
            parts_replaced=parts_replaced or [],
            performed_by=user.id,
            performed_at=datetime.now(timezone.utc),
            safety_state=safety_state,
            result=result,
            evidence_hash=digest,
            correction_of_id=correction_of_id,
            version=version,
            metadata_json={"immutable": True},
        ))

    @staticmethod
    def _prerequisites_satisfied(step, all_steps) -> bool:
        if not step.prerequisites:
            previous = [item for item in all_steps if item.sequence < step.sequence and item.is_required]
            return all(item.status in {"COMPLETED", "SKIPPED_WITH_REASON"} for item in previous)
        by_public_id = {item.sop_step_id: item for item in all_steps}
        for prerequisite in step.prerequisites:
            item = by_public_id.get(str(prerequisite))
            if item and item.status not in {"COMPLETED", "SKIPPED_WITH_REASON"}:
                return False
        return True
