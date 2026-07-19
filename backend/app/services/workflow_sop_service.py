from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AgentApproval, AgentArtifact, AgentRun, User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.agent import AgentArtifactConversionRequest
from app.schemas.maintenance_workflow import WorkflowSopDraftRequest, WorkflowSopReviewRequest
from app.services.agent_artifact_conversion_service import (
    AgentArtifactConversionPermissionError,
    AgentArtifactConversionService,
    AgentArtifactConversionServiceError,
)
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService


class WorkflowSopService:
    CREATE_OPERATION = "CREATE_SOP_DRAFT"
    REVIEW_OPERATION = "REVIEW_SOP"

    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()

    def create_draft(self, workflow_id: str, payload: WorkflowSopDraftRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.CREATE_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "SOP_DRAFT":
            raise MaintenanceWorkflowError("SOP draft can only be generated after diagnosis review")
        case = self.repository.get_case(workflow.case_id)
        diagnosis = self.repository.get_diagnosis(workflow.diagnosis_id)
        if not case or not diagnosis:
            raise MaintenanceWorkflowError("diagnosis context is missing")
        snapshot = workflow.diagnosis_snapshot or {}
        citations = list(snapshot.get("citations") or diagnosis.references or [])
        safety = list(snapshot.get("safety_warnings") or diagnosis.safety_notes or [])
        high_risk = case.safety_level in {"HIGH", "CRITICAL", "STOP_WORK"}
        decision = self.policy.can_create_sop(
            diagnosis_status=workflow.diagnosis_status,
            citation_count=len(citations),
            safety_count=len(safety),
            device_model_confirmed=bool(
                case.device_model
                or (snapshot.get("confirmed_fields") or {}).get("device_model")
                or (case.user_confirmed_facts or {}).get("device_model")
                or workflow.device_id
            ),
            open_high_conflicts=len(self.repository.list_open_high_conflicts(workflow.case_id)),
            high_risk=high_risk,
            expert_reviewed=bool(snapshot.get("expert_reviewed")),
        )
        if not decision.allowed:
            before = self.workflows.workflow_snapshot(workflow)
            workflow.status = "WAITING_EXPERT" if decision.required_role == "expert" else "BLOCKED"
            workflow.blocking_reason = "; ".join(decision.reasons)
            workflow.required_action = decision.required_action
            workflow.lock_version += 1
            self.repository.save_workflow(workflow)
            result = {"workflow": self.workflows.workflow_snapshot(workflow), "artifact": None, "policy": decision.as_dict()}
            self.workflows.record_event(
                workflow,
                user,
                event_type="SOP_DRAFT_BLOCKED",
                operation=self.CREATE_OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=workflow.blocking_reason,
                result=result,
            )
            self.db.commit()
            return result

        latest = self.repository.latest_artifact(workflow.workflow_id, "sop_draft")
        latest_approval = self.repository.get_approval_for_artifact(latest) if latest else None
        if (
            latest
            and latest_approval
            and latest_approval.status == "pending"
            and int((latest.content_json or {}).get("diagnosis_version") or -1) == workflow.diagnosis_version
        ):
            result = {
                "workflow": self.workflows.workflow_snapshot(workflow),
                "artifact": self.workflows.artifact_payload(latest),
                "approval_id": str(latest_approval.id),
                "approval_status": latest_approval.status,
                "policy": decision.as_dict(),
                "idempotent_replay": True,
            }
            return result

        version = workflow.sop_version + 1
        content = self._build_content(workflow, case, diagnosis, citations, safety, version)
        run_id = f"wf-sop-{hashlib.sha256(f'{workflow.workflow_id}:{version}'.encode()).hexdigest()[:24]}"
        run = self.repository.get_agent_run(run_id)
        if not run:
            run = self.repository.create_agent_run(AgentRun(
                run_id=run_id,
                agent_code="task25d_workflow_sop",
                user_id=user.id,
                device_id=workflow.device_id,
                status="SUCCEEDED",
                input_text=diagnosis.fault_description,
                input_media_ids_json=[],
                context_json={
                    "workflow_id": workflow.workflow_id,
                    "case_id": workflow.case_id,
                    "diagnosis_id": str(diagnosis.id),
                    "manufacturer": diagnosis.manufacturer,
                    "product_series": diagnosis.product_series,
                    "device_type": diagnosis.device_type,
                    "fault_type": diagnosis.fault_type,
                    "task25c_status": "MULTIMODAL_BENCHMARK_INSUFFICIENT",
                    "dedicated_rerank_status": "DEFERRED_QWEN3_RERANK_CONFIG",
                },
                provider="deterministic_task25d",
                model_name="task25d_sop_source_assembler_v1",
                final_answer="SOP draft created from validated diagnosis evidence; human approval is required.",
                confidence=Decimal(str(min(float(diagnosis.confidence or 0.0), 0.99))),
                requires_human_approval=True,
                approval_status="pending",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            ))
        before = self.workflows.workflow_snapshot(workflow)
        artifact = self.repository.create_artifact(AgentArtifact(
            run_id=run.run_id,
            artifact_type="sop_draft",
            title=content["title"],
            content_text=None,
            content_json=content,
            source_type="maintenance_workflow",
            source_id=workflow.workflow_id,
        ))
        approval = self.repository.create_approval(AgentApproval(
            run_id=run.run_id,
            approval_type="sop_draft_review",
            requested_action="review_workflow_sop_draft",
            payload_json={
                "artifact_id": str(artifact.id),
                "workflow_id": workflow.workflow_id,
                "version": version,
                "content_hash": content["content_hash"],
                "high_risk": high_risk,
            },
            status="pending",
            requested_by=user.id,
        ))
        workflow.sop_draft_id = artifact.id
        workflow.sop_version = version
        self.workflows.transition_stage(
            workflow,
            "SOP_REVIEW",
            status="WAITING_EXPERT" if high_risk else "WAITING_ENGINEER",
            required_action="review SOP draft",
        )
        result = {
            "workflow": self.workflows.workflow_snapshot(workflow),
            "artifact": self.workflows.artifact_payload(artifact),
            "approval_id": str(approval.id),
            "approval_status": approval.status,
            "policy": decision.as_dict(),
            "automatic_approval": False,
        }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type="SOP_DRAFTED",
                operation=self.CREATE_OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.reason or "versioned SOP draft created",
                result=result,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, self.CREATE_OPERATION, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError("SOP draft concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"SOP draft write failed: {exc.__class__.__name__}") from exc

    def review(self, workflow_id: str, payload: WorkflowSopReviewRequest, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.REVIEW_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage != "SOP_REVIEW" or not workflow.sop_draft_id:
            raise MaintenanceWorkflowError("SOP review requires the current SOP draft")
        artifact = self.repository.get_artifact(workflow.sop_draft_id)
        if not artifact:
            raise MaintenanceWorkflowError("SOP draft artifact not found")
        approval = self.repository.get_approval_for_artifact(artifact, lock=True)
        if not approval:
            raise MaintenanceWorkflowError("SOP approval record not found")
        if approval.status != "pending":
            raise MaintenanceWorkflowError("SOP version has already been reviewed")
        case = self.repository.get_case(workflow.case_id)
        if not case:
            raise MaintenanceWorkflowError("workflow case not found")
        high_risk = case.safety_level in {"HIGH", "CRITICAL", "STOP_WORK"}
        decision = self.policy.can_review_sop(actor_role=user.role, high_risk=high_risk)
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))
        content = artifact.content_json or {}
        if not content.get("citations") or not content.get("safety_requirements") or not content.get("steps"):
            raise MaintenanceWorkflowError("SOP draft source or safety coverage is incomplete")
        if self.repository.list_open_high_conflicts(workflow.case_id):
            raise MaintenanceWorkflowError("unresolved high-risk evidence conflict blocks SOP review")
        if int(content.get("diagnosis_version") or -1) != workflow.diagnosis_version:
            raise MaintenanceWorkflowError("SOP draft is stale because diagnosis changed")
        before = self.workflows.workflow_snapshot(workflow)
        approval.reviewed_by = user.id
        approval.review_comment = payload.comment
        approval.reviewed_at = datetime.now(timezone.utc)

        if payload.action == "APPROVE":
            approval.status = "approved"
            self.repository.save_approval(approval)
            try:
                conversion = AgentArtifactConversionService(self.db).convert_artifact(
                    artifact.id,
                    AgentArtifactConversionRequest(
                        target_type="sop_template",
                        approval_id=approval.id,
                        comment=payload.comment,
                    ),
                    current_user=user,
                    commit=False,
                )
            except (AgentArtifactConversionServiceError, AgentArtifactConversionPermissionError) as exc:
                raise MaintenanceWorkflowError(str(exc)) from exc
            if not conversion.target_id:
                raise MaintenanceWorkflowError("SOP conversion did not create a target")
            sop = self.repository.get_sop(self.workflows.uuid_list([conversion.target_id])[0])
            if not sop:
                raise MaintenanceWorkflowError("converted SOP not found")
            sop.status = "active"
            sop.version = workflow.sop_version
            sop.metadata_json = {
                **(sop.metadata_json or {}),
                "workflow_id": workflow.workflow_id,
                "case_id": workflow.case_id,
                "diagnosis_id": str(workflow.diagnosis_id),
                "diagnosis_version": workflow.diagnosis_version,
                "content_hash": content.get("content_hash"),
                "reviewed_by": str(user.id),
                "reviewed_role": user.role,
                "review_comment": payload.comment,
            }
            self.db.add(sop)
            workflow.approved_sop_id = sop.id
            self.workflows.transition_stage(
                workflow,
                "TASK_DRAFT",
                status="ACTIVE",
                required_action="generate task draft",
            )
            event_type = "SOP_REVIEWED"
            result = {
                "workflow": self.workflows.workflow_snapshot(workflow),
                "approval_status": approval.status,
                "approved_sop": self.workflows.sop_payload(sop),
                "conversion_trace_id": conversion.conversion_trace_id,
                "automatic_approval": False,
            }
        else:
            approval.status = {
                "REJECT": "rejected",
                "REQUEST_CHANGES": "changes_requested",
                "CREATE_NEW_VERSION": "superseded",
            }[payload.action]
            self.repository.save_approval(approval)
            self.workflows.transition_stage(
                workflow,
                "SOP_DRAFT",
                status="ACTIVE",
                required_action="create a new SOP version",
            )
            event_type = "SOP_REVIEWED"
            result = {
                "workflow": self.workflows.workflow_snapshot(workflow),
                "approval_status": approval.status,
                "approved_sop": None,
                "automatic_approval": False,
            }
        try:
            self.workflows.record_event(
                workflow,
                user,
                event_type=event_type,
                operation=self.REVIEW_OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.comment,
                result=result,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, self.REVIEW_OPERATION, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError("SOP review concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(f"SOP review failed: {exc.__class__.__name__}") from exc

    @staticmethod
    def _build_content(workflow, case, diagnosis, citations: list[dict], safety: list, version: int) -> dict:
        citation_ids = []
        for index, item in enumerate(citations, start=1):
            citation_ids.append(str(item.get("citation_id") or f"citation-{index}"))
        actions = list(dict.fromkeys([
            *(diagnosis.inspection_steps or []),
            *(diagnosis.recommended_actions or []),
        ]))
        steps = [
            {
                "step_id": f"step-{index}",
                "sequence": index,
                "title": action[:120],
                "action": action,
                "source_citation_ids": citation_ids,
                "is_required": True,
                "is_safety_step": index == 1,
                "prerequisites": ["确认设备与现场状态满足安全要求"] if index == 1 else [f"step-{index - 1}"],
                "verification_required": index == len(actions),
            }
            for index, action in enumerate(actions, start=1)
            if action
        ]
        if not steps:
            raise MaintenanceWorkflowError("diagnosis contains no source-grounded SOP steps")
        content = {
            "workflow_id": workflow.workflow_id,
            "case_id": workflow.case_id,
            "diagnosis_id": str(diagnosis.id),
            "diagnosis_version": workflow.diagnosis_version,
            "version": version,
            "title": f"{case.device_model or diagnosis.model or '设备'} {diagnosis.fault_type or '故障'} 检修 SOP 草稿",
            "manufacturer": diagnosis.manufacturer,
            "product_series": diagnosis.product_series,
            "device_type": diagnosis.device_type,
            "fault_type": diagnosis.fault_type,
            "maintenance_level": "level_2",
            "applicable_model": case.device_model or diagnosis.model,
            "fault_summary": diagnosis.fault_description,
            "prerequisites": ["由具备资质的工程人员确认停送电、隔离和现场作业条件。"],
            "tools_required": [],
            "materials_required": [],
            "safety_requirements": safety,
            "steps": steps,
            "ordered_steps": steps,
            "verification_steps": [step for step in steps if step.get("verification_required")],
            "abort_conditions": ["出现人身安全风险、设备状态异常扩大或证据与设备不一致时立即停止。"],
            "citations": citations,
            "evidence_ids": list(workflow.diagnosis_snapshot.get("supporting_evidence") or []),
            "source_semantic_units": [
                item.get("semantic_unit_id") for item in citations if item.get("semantic_unit_id")
            ],
            "requires_human_approval": True,
            "approval_status": "PENDING",
            "safety_level": case.safety_level,
            "mocked_evidence_used": False,
            "unreviewed_ai_evidence_used": False,
            "compliance_notes": "Task 25D workflow draft; no automatic approval or execution.",
        }
        digest_payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        content["content_hash"] = hashlib.sha256(digest_payload.encode("utf-8")).hexdigest()
        return content
