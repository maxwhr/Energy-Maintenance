from __future__ import annotations

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ModelOutputCorrection, User
from app.repositories.maintenance_workflow_repository import MaintenanceWorkflowRepository
from app.schemas.maintenance_workflow import WorkflowCorrectionCandidateRequest
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowError, MaintenanceWorkflowService


class WorkflowCorrectionService:
    """Creates review-only correction drafts backed by the existing correction model."""

    CREATE_OPERATION = "CREATE_CORRECTION_CANDIDATE"

    def __init__(self, db: Session):
        self.db = db
        self.repository = MaintenanceWorkflowRepository(db)
        self.workflows = MaintenanceWorkflowService(db)
        self.policy = MaintenanceWorkflowPolicyService()

    def create_candidate(
        self,
        workflow_id: str,
        payload: WorkflowCorrectionCandidateRequest,
        user: User,
    ) -> dict:
        workflow = self.workflows.get(workflow_id, user, lock=True)
        self.workflows.ensure_write_access(workflow, user, allow_terminal_replay=True)
        replay = self.workflows.idempotent_replay(workflow, self.CREATE_OPERATION, payload.idempotency_key)
        if replay:
            return replay
        self.workflows.ensure_write_access(workflow, user)
        if workflow.current_stage not in {"TASK_COMPLETED", "CORRECTION_REVIEW"}:
            raise MaintenanceWorkflowError("correction candidate requires a completed task")
        if not workflow.formal_task_id or not workflow.actual_result:
            raise MaintenanceWorkflowError("completed task evidence is missing")

        valid_evidence = self._valid_evidence_ids(workflow)
        requested_evidence = {str(value) for value in payload.evidence_ids}
        missing = sorted(requested_evidence - valid_evidence)
        if missing:
            raise MaintenanceWorkflowError(
                "correction evidence must belong to the workflow: " + ", ".join(missing[:5])
            )
        decision = self.policy.can_create_correction(
            task_completed=True,
            evidence_count=len(requested_evidence),
        )
        if not decision.allowed:
            raise MaintenanceWorkflowError("; ".join(decision.reasons))

        before = self.workflows.workflow_snapshot(workflow)
        correction = ModelOutputCorrection(
            source_type="maintenance_workflow",
            source_trace_id=workflow.workflow_id,
            original_output={
                "initial_diagnosis": workflow.diagnosis_snapshot or {},
                "actual_result": workflow.actual_result or {},
            },
            corrected_output=payload.proposed_change,
            correction_reason=payload.reason,
            submitted_by=user.id,
            review_status="draft",
            metadata_json={
                "workflow_id": workflow.workflow_id,
                "case_id": workflow.case_id,
                "task_id": str(workflow.formal_task_id),
                "candidate_type": payload.candidate_type,
                "source_document_ids": [str(value) for value in payload.source_document_ids],
                "source_chunk_ids": [str(value) for value in payload.source_chunk_ids],
                "semantic_unit_ids": payload.semantic_unit_ids,
                "evidence_ids": sorted(requested_evidence),
                "execution_record_ids": sorted(
                    requested_evidence & self._execution_record_ids(workflow.workflow_id)
                ),
                "status": "DRAFT",
                "expert_verified": False,
                "automatic_knowledge_update": False,
            },
        )
        try:
            self.repository.create_correction(correction)
            ids = list(workflow.correction_candidate_ids or [])
            ids.append(str(correction.id))
            workflow.correction_candidate_ids = list(dict.fromkeys(ids))
            self.workflows.transition_stage(
                workflow,
                "CORRECTION_REVIEW",
                status="WAITING_EXPERT",
                blocking_reason=None,
                required_action="review correction draft through the existing correction/curator flow",
            )
            result = {
                "workflow": self.workflows.workflow_snapshot(workflow),
                "correction": self.workflows.correction_payload(correction),
                "formal_knowledge_changed": False,
                "expert_verified": False,
            }
            self.workflows.record_event(
                workflow,
                user,
                event_type="CORRECTION_CREATED",
                operation=self.CREATE_OPERATION,
                idempotency_key=payload.idempotency_key,
                before=before,
                after=self.workflows.workflow_snapshot(workflow),
                reason=payload.reason,
                result=result,
                task_id=workflow.formal_task_id,
            )
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            workflow = self.workflows.get(workflow_id, user)
            replay = self.workflows.idempotent_replay(workflow, self.CREATE_OPERATION, payload.idempotency_key)
            if replay:
                return replay
            raise MaintenanceWorkflowError("correction candidate concurrency conflict") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MaintenanceWorkflowError(
                f"correction candidate creation failed: {exc.__class__.__name__}"
            ) from exc

    def list_candidates(self, workflow_id: str, user: User) -> dict:
        workflow = self.workflows.get(workflow_id, user)
        ids = self.workflows.uuid_list(workflow.correction_candidate_ids)
        items = self.repository.list_corrections(ids)
        return {
            "items": [self.workflows.correction_payload(item) for item in items],
            "total": len(items),
            "formal_knowledge_changed": False,
        }

    def _valid_evidence_ids(self, workflow) -> set[str]:
        ids = self._execution_record_ids(workflow.workflow_id)
        ids.update(str(item.id) for item in self.repository.list_evidence(workflow.case_id))
        ids.update(str(value) for value in (workflow.actual_result or {}).get("new_media_ids", []))
        return ids

    def _execution_record_ids(self, workflow_id: str) -> set[str]:
        ids: set[str] = set()
        for item in self.repository.list_execution_records(workflow_id):
            ids.add(str(item.id))
            ids.add(item.record_id)
            ids.update(str(value) for value in (item.media_ids or []))
        return ids
