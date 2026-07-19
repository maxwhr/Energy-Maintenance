from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AgentApproval, AgentArtifact, AgentRun, MaintenanceTaskStepExecution, SOPExecutionRecord, User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.agent import AgentArtifactConversionRequest
from app.schemas.maintenance_workflow import FormalTaskCreationRequest, WorkflowTaskDraftRequest
from app.services.agent_artifact_conversion_service import (
    AgentArtifactConversionPermissionError,
    AgentArtifactConversionService,
    AgentArtifactConversionServiceError,
)
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService


class FormalTaskCreationService:
    DRAFT_OPERATION = "CREATE_TASK_DRAFT"
    FORMAL_OPERATION = "CREATE_FORMAL_TASK"

    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()

    def create_task_draft(self, workflow_id: str, payload: WorkflowTaskDraftRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.DRAFT_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "TASK_DRAFT":
            raise MaintenanceWorkflowError("task draft requires SOP review stage completion")
        sop = self.repository.get_sop(workflow.approved_sop_id)
        decision = self.policy.can_create_task_draft(
            approved_sop=bool(sop and sop.status == "active"),
            personal_preparation_confirmed=payload.personal_preparation_confirmed,
        )
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))
        diagnosis = self.repository.get_diagnosis(workflow.diagnosis_id)
        case = self.repository.get_case(workflow.case_id)
        if not diagnosis or not case:
            raise MaintenanceWorkflowError("workflow diagnosis context is missing")

        latest = self.repository.latest_artifact(workflow.workflow_id, "task_draft")
        if latest:
            latest_content = dict(latest.content_json or {})
            if latest_content.get("approved_sop_id") == (str(workflow.approved_sop_id) if workflow.approved_sop_id else None):
                approval = self.repository.get_approval_for_artifact(latest)
                return {
                    "workflow": self.workflows.workflow_snapshot(workflow),
                    "artifact": self.workflows.artifact_payload(latest),
                    "approval_id": str(approval.id) if approval else None,
                    "approval_status": approval.status if approval else None,
                    "policy": decision.as_dict(),
                    "idempotent_replay": True,
                }
            latest_content["status"] = "STALE"
            latest_content["stale_reason"] = "approved SOP changed"
            latest.content_json = latest_content
            self.db.add(latest)

        version = workflow.task_draft_version + 1
        steps = list((sop.steps if sop else []) or [])
        citations = list((workflow.diagnosis_snapshot or {}).get("citations") or diagnosis.references or [])
        safety = list((sop.safety_requirements if sop else []) or diagnosis.safety_notes or [])
        content = {
            "workflow_id": workflow.workflow_id,
            "case_id": workflow.case_id,
            "device_id": str(workflow.device_id) if workflow.device_id else None,
            "diagnosis_id": str(diagnosis.id),
            "approved_sop_id": str(workflow.approved_sop_id) if workflow.approved_sop_id else None,
            "sop_version": sop.version if sop else None,
            "version": version,
            "title": payload.title or f"{case.device_model or diagnosis.model or '设备'} 检修任务草稿",
            "description": diagnosis.fault_description,
            "manufacturer": diagnosis.manufacturer,
            "product_series": diagnosis.product_series,
            "device_type": diagnosis.device_type,
            "model": diagnosis.model or case.device_model,
            "fault_type": diagnosis.fault_type,
            "alarm_code": diagnosis.alarm_code,
            "safety_requirements": safety,
            "required_tools": list((sop.tools_required if sop else []) or []),
            "required_parts": list((sop.materials_required if sop else []) or []),
            "planned_steps": steps,
            "suggested_steps": steps,
            "verification_requirements": [
                step for step in steps if isinstance(step, dict) and step.get("verification_required")
            ] or ["完成后验证设备状态并记录测量值与现场图片。"],
            "evidence_summary": {
                "diagnosis_status": workflow.diagnosis_status,
                "supporting_evidence_ids": (workflow.diagnosis_snapshot or {}).get("supporting_evidence") or [],
            },
            "citations": citations,
            "assignee_role": payload.assignee_role,
            "suggested_assignee_id": None,
            "priority": payload.priority,
            "status": "DRAFT",
            "requires_human_creation": True,
            "personal_preparation_only": not bool(workflow.approved_sop_id),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "mocked_evidence_used": False,
            "unreviewed_ai_evidence_used": False,
        }
        run_id = f"wf-task-{hashlib.sha256(f'{workflow.workflow_id}:{version}'.encode()).hexdigest()[:24]}"
        run = self.repository.get_agent_run(run_id)
        if not run:
            run = self.repository.create_agent_run(AgentRun(
                run_id=run_id,
                agent_code="task25d_workflow_task_draft",
                user_id=user.id,
                device_id=workflow.device_id,
                status="SUCCEEDED",
                input_text=diagnosis.fault_description,
                input_media_ids_json=list(case.media_ids or []),
                context_json={
                    "workflow_id": workflow.workflow_id,
                    "case_id": workflow.case_id,
                    "diagnosis_id": str(diagnosis.id),
                    "approved_sop_id": str(workflow.approved_sop_id) if workflow.approved_sop_id else None,
                    "manufacturer": diagnosis.manufacturer,
                    "product_series": diagnosis.product_series,
                    "device_type": diagnosis.device_type,
                    "fault_type": diagnosis.fault_type,
                },
                provider="deterministic_task25d",
                model_name="task25d_task_draft_assembler_v1",
                final_answer="Task draft created; explicit formal task creation is required.",
                confidence=Decimal(str(min(float(diagnosis.confidence or 0.0), 0.99))),
                requires_human_approval=True,
                approval_status="pending",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            ))
        before = self.workflows.workflow_snapshot(workflow)
        artifact = self.repository.create_artifact(AgentArtifact(
            run_id=run.run_id,
            artifact_type="task_draft",
            title=content["title"],
            content_text=None,
            content_json=content,
            source_type="maintenance_workflow",
            source_id=workflow.workflow_id,
        ))
        approval = self.repository.create_approval(AgentApproval(
            run_id=run.run_id,
            approval_type="task_draft_review",
            requested_action="create_formal_task",
            payload_json={
                "artifact_id": str(artifact.id),
                "workflow_id": workflow.workflow_id,
                "version": version,
                "approved_sop_id": content["approved_sop_id"],
            },
            status="pending",
            requested_by=user.id,
        ))
        workflow.task_draft_id = artifact.id
        workflow.task_draft_version = version
        workflow.status = "WAITING_ENGINEER"
        workflow.required_action = "explicitly create formal task"
        workflow.lock_version += 1
        self.repository.save_workflow(workflow)
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "artifact": self.workflows.artifact_payload(artifact),
            "approval_id": str(approval.id),
            "approval_status": approval.status,
            "policy": decision.as_dict(),
            "automatic_formal_task": False,
        }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type="TASK_DRAFTED",
                operation=self.DRAFT_OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.comment or "task draft created",
                result=result,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, self.DRAFT_OPERATION, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError("task draft concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"task draft write failed: {exc.__class__.__name__}") from exc

    def create_formal_task(self, workflow_id: str, payload: FormalTaskCreationRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.FORMAL_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.formal_task_id:
            result = self.workflows.to_detail(workflow, user)
            result["idempotent_replay"] = True
            result["duplicate_prevented"] = True
            return result
        if workflow.current_stage != "TASK_DRAFT" or not workflow.task_draft_id:
            raise MaintenanceWorkflowError("formal task requires a valid task draft")
        artifact = self.repository.get_artifact(workflow.task_draft_id)
        sop = self.repository.get_sop(workflow.approved_sop_id)
        device = self.repository.get_device(workflow.device_id)
        if not artifact:
            raise MaintenanceWorkflowError("task draft artifact not found")
        content = dict(artifact.content_json or {})
        expires_at = datetime.fromisoformat(content["expires_at"]) if content.get("expires_at") else None
        task_draft_valid = (
            content.get("status") == "DRAFT"
            and content.get("approved_sop_id") == (str(workflow.approved_sop_id) if workflow.approved_sop_id else None)
            and (expires_at is None or expires_at > datetime.now(timezone.utc))
        )
        assignee = self.repository.get_user(payload.assignee_id) if payload.assignee_id else None
        assignee_valid = assignee is None or (
            assignee.role in {"engineer", "expert", "admin"}
            and assignee.status == "active"
            and bool(assignee.is_active)
        )
        decision = self.policy.can_create_formal_task(
            actor_role=user.role,
            task_draft_valid=task_draft_valid,
            sop_approved=bool(sop and sop.status == "active"),
            device_exists=bool(device and getattr(device, "status", "active") not in {"archived", "retired"}),
            safety_present=bool(content.get("safety_requirements")),
            verification_present=bool(content.get("verification_requirements")),
            citations_present=bool(content.get("citations")),
            assignee_valid=assignee_valid,
        )
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))
        approval = self.repository.get_approval_for_artifact(artifact, lock=True)
        if not approval:
            raise MaintenanceWorkflowError("task draft approval record not found")
        if approval.status != "pending":
            raise MaintenanceWorkflowError("task draft approval has already been finalized")
        before = self.workflows.workflow_snapshot(workflow)
        approval.status = "approved"
        approval.reviewed_by = user.id
        approval.review_comment = payload.comment
        approval.reviewed_at = datetime.now(timezone.utc)
        self.repository.save_approval(approval)
        if payload.assignee_id:
            content["suggested_assignee_id"] = str(payload.assignee_id)
            artifact.content_json = content
            self.db.add(artifact)
        try:
            conversion = AgentArtifactConversionService(self.db).convert_artifact(
                artifact.id,
                AgentArtifactConversionRequest(
                    target_type="maintenance_task",
                    approval_id=approval.id,
                    comment=payload.comment,
                ),
                current_user=user,
                commit=False,
            )
        except (AgentArtifactConversionServiceError, AgentArtifactConversionPermissionError) as exc:
            raise MaintenanceWorkflowError(str(exc)) from exc
        if not conversion.target_id:
            raise MaintenanceWorkflowError("formal task conversion did not create a task")
        task_ids = self.workflows.uuid_list([conversion.target_id])
        task = self.repository.get_task(task_ids[0] if task_ids else None, lock=True)
        if not task:
            raise MaintenanceWorkflowError("formal task not found after conversion")
        task.device_id = workflow.device_id
        task.sop_template_id = workflow.approved_sop_id
        task.source_type = "maintenance_workflow"
        task.source_trace_id = workflow.workflow_id
        task.assignee_id = assignee.id if assignee else None
        task.assignee = (assignee.display_name or assignee.username) if assignee else None
        task.suggested_steps = list(content.get("planned_steps") or [])
        task.result_summary = "Formal task created by explicit workflow action; execution has not started."
        self.repository.save_task(task)
        execution = SOPExecutionRecord(
            task_id=task.id,
            template_id=sop.id,
            executor_id=assignee.id if assignee else None,
            step_results=[],
            status="not_started",
            metadata_json={
                "workflow_id": workflow.workflow_id,
                "case_id": workflow.case_id,
                "diagnosis_id": str(workflow.diagnosis_id),
            },
        )
        self.db.add(execution)
        self.db.flush()
        task.sop_execution_id = execution.id
        self.repository.save_task(task)
        for index, raw_step in enumerate(content.get("planned_steps") or [], start=1):
            step = raw_step if isinstance(raw_step, dict) else {"action": str(raw_step)}
            self.repository.create_step(MaintenanceTaskStepExecution(
                workflow_id=workflow.workflow_id,
                task_id=task.id,
                sop_step_id=str(step.get("step_id") or f"step-{index}"),
                sequence=int(step.get("sequence") or index),
                status="PENDING",
                verification_status="PENDING",
                is_required=bool(step.get("is_required", True)),
                is_safety_step=bool(step.get("is_safety_step", False)),
                prerequisites=list(step.get("prerequisites") or []),
                metadata_json={
                    "title": step.get("title"),
                    "action": step.get("action"),
                    "verification_required": bool(step.get("verification_required")),
                    "source_citation_ids": list(step.get("source_citation_ids") or []),
                },
            ))
        workflow.formal_task_id = task.id
        self.workflows.transition_stage(
            workflow,
            "TASK_CREATED",
            status="ACTIVE",
            required_action="start formal task",
        )
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "formal_task": self.workflows.task_payload(task),
            "step_count": len(self.repository.list_steps(workflow.workflow_id)),
            "conversion_trace_id": conversion.conversion_trace_id,
            "policy": decision.as_dict(),
            "automatic_formal_task": False,
        }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type="TASK_CREATED",
                operation=self.FORMAL_OPERATION,
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
            replay = self.workflows.idempotent_replay(workflow, self.FORMAL_OPERATION, payload.idempotency_key)
            if replay:
                return replay
            if workflow.formal_task_id:
                result = self.workflows.to_detail(workflow, user)
                result["duplicate_prevented"] = True
                return result
            raise MaintenanceWorkflowError("formal task concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"formal task creation failed: {exc.__class__.__name__}") from exc
