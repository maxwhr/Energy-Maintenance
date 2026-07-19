from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import MaintenanceWorkflow, MaintenanceWorkflowEvent, OperationLog, User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.maintenance_workflow import MaintenanceWorkflowCreate, WorkflowAdminActionRequest
from app.services.maintenance_workflow_policy_service import (
    MaintenanceWorkflowPolicyService,
    TERMINAL_WORKFLOW_STATUSES,
)


class MaintenanceWorkflowError(ValueError):
    pass


class MaintenanceWorkflowPermissionError(PermissionError):
    pass


class MaintenanceWorkflowService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.policy = MaintenanceWorkflowPolicyService()

    def create(self, payload: MaintenanceWorkflowCreate, user: User) -> dict:
        if user.role not in self.policy.WRITE_ROLES:
            raise MaintenanceWorkflowPermissionError("viewer cannot create a maintenance workflow")
        existing = self.repository.get_by_idempotency_key(payload.idempotency_key)
        if existing:
            self.ensure_read_access(existing, user)
            result = self.to_detail(existing, user)
            result["idempotent_replay"] = True
            return result
        case = self.repository.get_case(payload.case_id)
        if not case:
            raise MaintenanceWorkflowError("multimodal maintenance case not found")
        if user.role not in {"admin", "expert"} and case.created_by != user.id:
            raise MaintenanceWorkflowPermissionError("cannot create workflow for another user's case")
        active = self.repository.get_active_by_case(case.case_id)
        if active:
            self.ensure_read_access(active, user)
            result = self.to_detail(active, user)
            result["idempotent_replay"] = True
            result["reused_active_workflow"] = True
            return result
        device_id = payload.device_id or case.device_id
        if device_id and not self.repository.get_device(device_id):
            raise MaintenanceWorkflowError("device not found")
        stage, status, required_action = self._initial_state(case.status)
        workflow = MaintenanceWorkflow(
            workflow_id=f"mwf_{uuid4().hex}",
            case_id=case.case_id,
            idempotency_key=payload.idempotency_key,
            device_id=device_id,
            current_stage=stage,
            status=status,
            required_action=required_action,
            diagnosis_status="DRAFT",
            created_by=user.id,
            metadata_json={
                "task25c_status": "MULTIMODAL_BENCHMARK_INSUFFICIENT",
                "dedicated_rerank_status": "DEFERRED_QWEN3_RERANK_CONFIG",
                "automatic_diagnosis_confirmation": False,
                "automatic_sop_approval": False,
                "automatic_formal_task_creation": False,
                "automatic_task_completion": False,
                "automatic_knowledge_update": False,
            },
        )
        try:
            self.repository.create_workflow(workflow)
            result = self.to_detail(workflow, user, include_timeline=False)
            self.record_event(
                workflow,
                user,
                event_type="CASE_CREATED",
                operation="CREATE_WORKFLOW",
                idempotency_key=payload.idempotency_key,
                before={},
                after=self.workflow_snapshot(workflow),
                reason=payload.reason or "maintenance workflow created",
                result=result,
            )
            self.db.commit()
            return self.to_detail(workflow, user)
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.repository.get_by_idempotency_key(payload.idempotency_key) or self.repository.get_active_by_case(case.case_id)
            if existing:
                result = self.to_detail(existing, user)
                result["idempotent_replay"] = True
                return result
            raise MaintenanceWorkflowError("workflow create conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"workflow create failed: {exc.__class__.__name__}") from exc

    def list(
        self,
        *,
        user: User,
        status: str | None,
        device_id: UUID | None,
        page: int,
        page_size: int,
    ) -> dict:
        self._validate_page(page, page_size)
        items, total = self.repository.list_workflows(
            visible_user=user,
            status=status,
            device_id=device_id,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [self.to_summary(item, user) for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get(self, workflow_id: str, user: User, *, lock: bool = False) -> MaintenanceWorkflow:
        workflow = self.repository.get_workflow(workflow_id, lock=lock)
        if not workflow:
            raise MaintenanceWorkflowError("maintenance workflow not found")
        self.ensure_read_access(workflow, user)
        return workflow

    def detail(self, workflow_id: str, user: User) -> dict:
        return self.to_detail(self.get(workflow_id, user), user)

    def status(self, workflow_id: str, user: User) -> dict:
        workflow = self.get(workflow_id, user)
        return {
            **self.workflow_snapshot(workflow),
            "allowed_actions": self.allowed_actions(workflow, user),
        }

    def timeline(self, workflow_id: str, user: User) -> dict:
        workflow = self.get(workflow_id, user)
        events = self.repository.list_events(workflow.workflow_id)
        return {
            "items": [self.event_payload(item) for item in events],
            "total": len(events),
            "audit_coverage": 1.0 if events else 0.0,
        }

    def admin_action(self, workflow_id: str, payload: WorkflowAdminActionRequest, user: User) -> dict:
        if user.role != "admin":
            raise MaintenanceWorkflowPermissionError("admin role required")
        workflow = self.get(workflow_id, user, lock=True)
        replay = self.idempotent_replay(workflow, f"ADMIN_{payload.action}", payload.idempotency_key)
        if replay:
            return replay
        before = self.workflow_snapshot(workflow)
        if payload.action == "UNBLOCK":
            if workflow.status != "BLOCKED":
                raise MaintenanceWorkflowError("only blocked workflow can be unblocked")
            workflow.status = "ACTIVE"
            workflow.blocking_reason = None
            workflow.required_action = "continue from current stage"
            event_type = "WORKFLOW_UNBLOCKED"
        elif payload.action == "CANCEL":
            if workflow.status in TERMINAL_WORKFLOW_STATUSES:
                raise MaintenanceWorkflowError("terminal workflow cannot be cancelled")
            workflow.status = "CANCELLED"
            workflow.blocking_reason = payload.reason
            workflow.required_action = None
            event_type = "WORKFLOW_CANCELLED"
        else:
            if workflow.status not in TERMINAL_WORKFLOW_STATUSES and workflow.current_stage not in {"TASK_COMPLETED", "CORRECTION_REVIEW"}:
                raise MaintenanceWorkflowError("active workflow cannot be archived before task completion")
            workflow.current_stage = "CLOSED"
            workflow.status = "COMPLETED"
            workflow.required_action = None
            event_type = "WORKFLOW_CLOSED"
        workflow.lock_version += 1
        self.repository.save_workflow(workflow)
        result = self.to_detail(workflow, user, include_timeline=False)
        self.record_event(
            workflow,
            user,
            event_type=event_type,
            operation=f"ADMIN_{payload.action}",
            idempotency_key=payload.idempotency_key,
            before=before,
            after=self.workflow_snapshot(workflow),
            reason=payload.reason,
            result=result,
        )
        self.db.commit()
        return self.to_detail(workflow, user)

    def transition_stage(
        self,
        workflow: MaintenanceWorkflow,
        target: str,
        *,
        status: str | None = None,
        blocking_reason: str | None = None,
        required_action: str | None = None,
    ) -> None:
        decision = self.policy.can_transition_stage(workflow.current_stage, target)
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))
        workflow.current_stage = target
        if status:
            workflow.status = status
        workflow.blocking_reason = blocking_reason
        workflow.required_action = required_action
        workflow.lock_version += 1
        self.repository.save_workflow(workflow)

    def idempotent_replay(self, workflow: MaintenanceWorkflow, operation: str, key: str) -> dict | None:
        event = self.repository.get_event_by_idempotency(workflow.workflow_id, operation, key)
        if not event:
            return None
        result = dict(event.result_json or {})
        result["idempotent_replay"] = True
        return result

    def record_event(
        self,
        workflow: MaintenanceWorkflow,
        user: User,
        *,
        event_type: str,
        operation: str,
        idempotency_key: str | None,
        before: dict,
        after: dict,
        reason: str | None,
        result: dict,
        task_id: UUID | None = None,
    ) -> MaintenanceWorkflowEvent:
        event = MaintenanceWorkflowEvent(
            event_id=f"wfe_{uuid4().hex}",
            workflow_id=workflow.workflow_id,
            case_id=workflow.case_id,
            task_id=task_id or workflow.formal_task_id,
            actor_id=user.id,
            actor_role=user.role,
            event_type=event_type,
            operation=operation,
            idempotency_key=idempotency_key,
            before_json=self.json_safe(before),
            after_json=self.json_safe(after),
            result_json=self.json_safe(result),
            reason=reason,
        )
        self.repository.create_event(event)
        self.repository.add_operation_log(OperationLog(
            module="maintenance_workflow",
            action=event_type,
            target_type="maintenance_workflow",
            target_id=workflow.workflow_id,
            operator=user.username,
            request_id=idempotency_key,
            trace_id=workflow.workflow_id,
            detail={
                "event_id": event.event_id,
                "actor_id": str(user.id),
                "actor_role": user.role,
                "before": self.json_safe(before),
                "after": self.json_safe(after),
                "reason": reason,
            },
        ))
        return event

    def ensure_read_access(self, workflow: MaintenanceWorkflow, user: User) -> None:
        if user.role in {"admin", "expert"}:
            return
        if workflow.created_by == user.id:
            return
        task = self.repository.get_task(workflow.formal_task_id)
        if task and task.assignee_id == user.id:
            return
        raise MaintenanceWorkflowPermissionError("maintenance workflow access denied")

    def ensure_write_access(
        self,
        workflow: MaintenanceWorkflow,
        user: User,
        *,
        allow_terminal_replay: bool = False,
    ) -> None:
        if user.role not in self.policy.WRITE_ROLES:
            raise MaintenanceWorkflowPermissionError("viewer cannot modify maintenance workflow")
        self.ensure_read_access(workflow, user)
        if workflow.status in TERMINAL_WORKFLOW_STATUSES and not allow_terminal_replay:
            raise MaintenanceWorkflowError("terminal workflow cannot be modified")

    def to_summary(self, workflow: MaintenanceWorkflow, user: User) -> dict:
        return {
            **self.workflow_snapshot(workflow),
            "allowed_actions": self.allowed_actions(workflow, user),
        }

    def to_detail(
        self,
        workflow: MaintenanceWorkflow,
        user: User,
        *,
        include_timeline: bool = True,
    ) -> dict:
        case = self.repository.get_case(workflow.case_id)
        diagnosis = self.repository.get_diagnosis(workflow.diagnosis_id)
        sop_draft = self.repository.get_artifact(workflow.sop_draft_id)
        sop = self.repository.get_sop(workflow.approved_sop_id)
        task_draft = self.repository.get_artifact(workflow.task_draft_id)
        task = self.repository.get_task(workflow.formal_task_id)
        steps = self.repository.list_steps(workflow.workflow_id)
        records = self.repository.list_execution_records(workflow.workflow_id)
        correction_ids = self.uuid_list(workflow.correction_candidate_ids)
        corrections = self.repository.list_corrections(correction_ids)
        result = {
            **self.workflow_snapshot(workflow),
            "allowed_actions": self.allowed_actions(workflow, user),
            "case": {
                "case_id": case.case_id,
                "title": case.title,
                "status": case.status,
                "device_model": case.device_model,
                "safety_level": case.safety_level,
                "confidence_status": case.confidence_status,
                "media_ids": case.media_ids,
                "citation_count": len(case.knowledge_citations or []),
            } if case else None,
            "diagnosis": self.diagnosis_payload(diagnosis),
            "diagnosis_snapshot": workflow.diagnosis_snapshot,
            "sop_draft": self.artifact_payload(sop_draft),
            "approved_sop": self.sop_payload(sop),
            "task_draft": self.artifact_payload(task_draft),
            "formal_task": self.task_payload(task),
            "steps": [self.step_payload(item) for item in steps],
            "execution_records": [self.execution_record_payload(item) for item in records],
            "corrections": [self.correction_payload(item) for item in corrections],
        }
        if include_timeline:
            events = self.repository.list_events(workflow.workflow_id)
            result["timeline"] = [self.event_payload(item) for item in events]
        return result

    def workflow_snapshot(self, workflow: MaintenanceWorkflow) -> dict:
        return {
            "workflow_id": workflow.workflow_id,
            "case_id": workflow.case_id,
            "device_id": str(workflow.device_id) if workflow.device_id else None,
            "diagnosis_id": str(workflow.diagnosis_id) if workflow.diagnosis_id else None,
            "diagnosis_hypothesis_id": str(workflow.diagnosis_hypothesis_id) if workflow.diagnosis_hypothesis_id else None,
            "sop_draft_id": str(workflow.sop_draft_id) if workflow.sop_draft_id else None,
            "approved_sop_id": str(workflow.approved_sop_id) if workflow.approved_sop_id else None,
            "task_draft_id": str(workflow.task_draft_id) if workflow.task_draft_id else None,
            "formal_task_id": str(workflow.formal_task_id) if workflow.formal_task_id else None,
            "record_id": str(workflow.record_id) if workflow.record_id else None,
            "correction_candidate_ids": workflow.correction_candidate_ids or [],
            "current_stage": workflow.current_stage,
            "status": workflow.status,
            "blocking_reason": workflow.blocking_reason,
            "required_action": workflow.required_action,
            "diagnosis_status": workflow.diagnosis_status,
            "diagnosis_version": workflow.diagnosis_version,
            "sop_version": workflow.sop_version,
            "task_draft_version": workflow.task_draft_version,
            "diagnosis_match_status": workflow.diagnosis_match_status,
            "lock_version": workflow.lock_version,
            "created_by": str(workflow.created_by),
            "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
            "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
        }

    def allowed_actions(self, workflow: MaintenanceWorkflow, user: User) -> list[dict]:
        all_actions = [
            "diagnosis-draft",
            "diagnosis-confirm",
            "sop-draft",
            "sop-review",
            "task-draft",
            "formal-task",
            "task/start",
            "task/pause",
            "task/resume",
            "task/records",
            "task/steps",
            "task/verify",
            "task/complete",
            "correction-candidate",
            "archive",
        ]
        mapping = {
            "CASE_ANALYSIS": ["diagnosis-draft"],
            "EVIDENCE_REVIEW": ["diagnosis-draft"],
            "DIAGNOSIS_REVIEW": ["diagnosis-confirm"],
            "SOP_DRAFT": ["sop-draft"],
            "SOP_REVIEW": ["sop-review"],
            "TASK_DRAFT": ["task-draft", "formal-task"],
            "TASK_CREATED": ["task/start"],
            "TASK_EXECUTION": ["task/pause", "task/resume", "task/records", "task/steps", "task/verify"],
            "RESULT_VERIFICATION": ["task/complete", "task/resume"],
            "TASK_COMPLETED": ["correction-candidate", "archive"],
            "CORRECTION_REVIEW": ["correction-candidate", "archive"],
        }
        stage_actions = set(mapping.get(workflow.current_stage, []))
        task = self.repository.get_task(workflow.formal_task_id)
        task_status = (task.status or task.task_status) if task else None
        if "formal-task" in stage_actions and not workflow.task_draft_id:
            stage_actions.remove("formal-task")
        if task_status == "paused":
            stage_actions.discard("task/pause")
            stage_actions.discard("task/steps")
            stage_actions.discard("task/verify")
        else:
            stage_actions.discard("task/resume")
        if user.role == "viewer":
            stage_actions.clear()
            common_reason = "viewer has read-only access"
        elif workflow.status in TERMINAL_WORKFLOW_STATUSES:
            stage_actions.clear()
            common_reason = "terminal workflow cannot be modified"
        else:
            common_reason = None
        return [
            {
                "action": action,
                "allowed": action in stage_actions and not (
                    action == "formal-task" and user.role not in self.policy.FORMAL_TASK_ROLES
                ),
                "disabled_reason": (
                    None
                    if action in stage_actions and not (
                        action == "formal-task" and user.role not in self.policy.FORMAL_TASK_ROLES
                    )
                    else common_reason
                    or ("engineer or admin role required" if action == "formal-task" else None)
                    or f"action is unavailable during {workflow.current_stage}"
                ),
            }
            for action in all_actions
        ]

    @staticmethod
    def event_payload(item: MaintenanceWorkflowEvent) -> dict:
        return {
            "event_id": item.event_id,
            "workflow_id": item.workflow_id,
            "case_id": item.case_id,
            "task_id": str(item.task_id) if item.task_id else None,
            "actor_id": str(item.actor_id),
            "actor_role": item.actor_role,
            "event_type": item.event_type,
            "before": item.before_json,
            "after": item.after_json,
            "reason": item.reason,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    @staticmethod
    def diagnosis_payload(item) -> dict | None:
        if not item:
            return None
        return {
            "id": str(item.id),
            "trace_id": item.trace_id,
            "fault_type": item.fault_type,
            "alarm_code": item.alarm_code,
            "fault_description": item.fault_description,
            "possible_causes": item.possible_causes,
            "inspection_steps": item.inspection_steps,
            "recommended_actions": item.recommended_actions,
            "safety_notes": item.safety_notes,
            "references": item.references,
            "confidence": item.confidence,
        }

    @staticmethod
    def artifact_payload(item) -> dict | None:
        if not item:
            return None
        return {
            "id": str(item.id),
            "run_id": item.run_id,
            "artifact_type": item.artifact_type,
            "title": item.title,
            "content": item.content_json,
            "source_type": item.source_type,
            "source_id": item.source_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    @staticmethod
    def sop_payload(item) -> dict | None:
        if not item:
            return None
        return {
            "id": str(item.id),
            "title": item.title,
            "status": item.status,
            "version": item.version,
            "steps": item.steps,
            "safety_requirements": item.safety_requirements,
            "metadata": item.metadata_json,
        }

    @staticmethod
    def task_payload(item) -> dict | None:
        if not item:
            return None
        return {
            "id": str(item.id),
            "title": item.title,
            "status": item.status,
            "task_status": item.task_status,
            "device_id": str(item.device_id) if item.device_id else None,
            "assignee_id": str(item.assignee_id) if item.assignee_id else None,
            "priority": item.priority,
            "sop_template_id": str(item.sop_template_id) if item.sop_template_id else None,
            "result_summary": item.result_summary,
            "verification_result": item.verification_result,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        }

    @staticmethod
    def step_payload(item) -> dict:
        return {
            "step_id": str(item.id),
            "task_id": str(item.task_id),
            "sop_step_id": item.sop_step_id,
            "sequence": item.sequence,
            "status": item.status,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            "performed_by": str(item.performed_by) if item.performed_by else None,
            "result_summary": item.result_summary,
            "evidence_ids": item.evidence_ids,
            "skip_reason": item.skip_reason,
            "verification_status": item.verification_status,
            "is_required": item.is_required,
            "is_safety_step": item.is_safety_step,
            "prerequisites": item.prerequisites,
        }

    @staticmethod
    def execution_record_payload(item) -> dict:
        return {
            "record_id": item.record_id,
            "id": str(item.id),
            "task_id": str(item.task_id),
            "step_id": str(item.step_execution_id) if item.step_execution_id else None,
            "record_type": item.record_type,
            "content": item.content,
            "media_ids": item.media_ids,
            "measurements": item.measurements,
            "parts_replaced": item.parts_replaced,
            "performed_by": str(item.performed_by),
            "performed_at": item.performed_at.isoformat() if item.performed_at else None,
            "safety_state": item.safety_state,
            "result": item.result,
            "evidence_hash": item.evidence_hash,
            "correction_of_id": str(item.correction_of_id) if item.correction_of_id else None,
            "version": item.version,
        }

    @staticmethod
    def correction_payload(item) -> dict:
        return {
            "id": str(item.id),
            "source_type": item.source_type,
            "source_trace_id": item.source_trace_id,
            "status": item.review_status,
            "reason": item.correction_reason,
            "proposed_change": item.corrected_output,
            "metadata": item.metadata_json,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    @staticmethod
    def json_safe(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): MaintenanceWorkflowService.json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [MaintenanceWorkflowService.json_safe(item) for item in value]
        return value

    @staticmethod
    def uuid_list(values: list) -> list[UUID]:
        result = []
        for value in values or []:
            try:
                result.append(UUID(str(value)))
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _initial_state(case_status: str) -> tuple[str, str, str | None]:
        if case_status in {"EVIDENCE_READY", "MULTIPLE_POSSIBILITIES", "DIAGNOSIS_READY"}:
            return "EVIDENCE_REVIEW", "ACTIVE", "generate diagnosis draft"
        if case_status == "NEEDS_CLARIFICATION":
            return "CASE_ANALYSIS", "WAITING_USER", "answer clarification questions"
        if case_status == "INSUFFICIENT_EVIDENCE":
            return "CASE_ANALYSIS", "BLOCKED", "add evidence and retrieve official knowledge"
        return "CASE_ANALYSIS", "ACTIVE", "analyze case evidence"

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if page < 1 or page_size < 1 or page_size > 100:
            raise MaintenanceWorkflowError("invalid pagination")
