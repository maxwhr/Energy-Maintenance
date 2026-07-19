from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentRun,
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    MaintenanceTask,
    MaintenanceTaskExecutionRecord,
    MaintenanceTaskStepExecution,
    MaintenanceWorkflow,
    MaintenanceWorkflowEvent,
    ModelOutputCorrection,
    MultimodalDiagnosticHypothesis,
    MultimodalEvidenceConflict,
    MultimodalEvidenceItem,
    MultimodalMaintenanceCase,
    OperationLog,
    SOPTemplate,
    SOPExecutionRecord,
    UploadedMedia,
    User,
)


TERMINAL_WORKFLOW_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}


class MaintenanceWorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_workflow(self, item: MaintenanceWorkflow) -> MaintenanceWorkflow:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save_workflow(self, item: MaintenanceWorkflow) -> MaintenanceWorkflow:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_workflow(self, workflow_id: str, *, lock: bool = False) -> MaintenanceWorkflow | None:
        statement = select(MaintenanceWorkflow).where(MaintenanceWorkflow.workflow_id == workflow_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def get_by_idempotency_key(self, key: str) -> MaintenanceWorkflow | None:
        return self.db.scalar(select(MaintenanceWorkflow).where(MaintenanceWorkflow.idempotency_key == key))

    def get_active_by_case(self, case_id: str) -> MaintenanceWorkflow | None:
        return self.db.scalar(
            select(MaintenanceWorkflow).where(
                MaintenanceWorkflow.case_id == case_id,
                MaintenanceWorkflow.status.not_in(TERMINAL_WORKFLOW_STATUSES),
            )
        )

    def list_workflows(
        self,
        *,
        visible_user: User,
        status: str | None,
        device_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[MaintenanceWorkflow], int]:
        filters = []
        if visible_user.role not in {"admin", "expert"}:
            filters.append(or_(
                MaintenanceWorkflow.created_by == visible_user.id,
                MaintenanceWorkflow.formal_task_id.in_(
                    select(MaintenanceTask.id).where(MaintenanceTask.assignee_id == visible_user.id)
                ),
            ))
        if status:
            filters.append(MaintenanceWorkflow.status == status)
        if device_id:
            filters.append(MaintenanceWorkflow.device_id == device_id)
        count_statement = select(func.count(MaintenanceWorkflow.id))
        list_statement = select(MaintenanceWorkflow)
        if filters:
            count_statement = count_statement.where(*filters)
            list_statement = list_statement.where(*filters)
        total = int(self.db.scalar(count_statement) or 0)
        items = list(self.db.scalars(
            list_statement.order_by(MaintenanceWorkflow.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ))
        return items, total

    def create_event(self, item: MaintenanceWorkflowEvent) -> MaintenanceWorkflowEvent:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_event_by_idempotency(
        self,
        workflow_id: str,
        operation: str,
        idempotency_key: str,
        *,
        lock: bool = False,
    ) -> MaintenanceWorkflowEvent | None:
        statement = select(MaintenanceWorkflowEvent).where(
            MaintenanceWorkflowEvent.workflow_id == workflow_id,
            MaintenanceWorkflowEvent.operation == operation,
            MaintenanceWorkflowEvent.idempotency_key == idempotency_key,
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_events(self, workflow_id: str) -> list[MaintenanceWorkflowEvent]:
        return list(self.db.scalars(
            select(MaintenanceWorkflowEvent)
            .where(MaintenanceWorkflowEvent.workflow_id == workflow_id)
            .order_by(MaintenanceWorkflowEvent.created_at, MaintenanceWorkflowEvent.id)
        ))

    def add_operation_log(self, item: OperationLog) -> OperationLog:
        self.db.add(item)
        self.db.flush()
        return item

    def get_case(self, case_id: str) -> MultimodalMaintenanceCase | None:
        return self.db.scalar(
            select(MultimodalMaintenanceCase).where(MultimodalMaintenanceCase.case_id == case_id)
        )

    def get_device(self, device_id: UUID | None) -> Device | None:
        return self.db.get(Device, device_id) if device_id else None

    def get_user(self, user_id: UUID | None) -> User | None:
        return self.db.get(User, user_id) if user_id else None

    def get_diagnosis(self, diagnosis_id: UUID | None) -> DiagnosisRecord | None:
        return self.db.get(DiagnosisRecord, diagnosis_id) if diagnosis_id else None

    def create_diagnosis(self, item: DiagnosisRecord) -> DiagnosisRecord:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_hypothesis_by_public_id(
        self, case_id: str, hypothesis_id: str
    ) -> MultimodalDiagnosticHypothesis | None:
        return self.db.scalar(select(MultimodalDiagnosticHypothesis).where(
            MultimodalDiagnosticHypothesis.case_id == case_id,
            MultimodalDiagnosticHypothesis.hypothesis_id == hypothesis_id,
        ))

    def list_hypotheses(self, case_id: str) -> list[MultimodalDiagnosticHypothesis]:
        return list(self.db.scalars(
            select(MultimodalDiagnosticHypothesis)
            .where(MultimodalDiagnosticHypothesis.case_id == case_id)
            .order_by(MultimodalDiagnosticHypothesis.confidence.desc())
        ))

    def save_hypothesis(self, item: MultimodalDiagnosticHypothesis) -> MultimodalDiagnosticHypothesis:
        self.db.add(item)
        self.db.flush()
        return item

    def list_open_high_conflicts(self, case_id: str) -> list[MultimodalEvidenceConflict]:
        return list(self.db.scalars(select(MultimodalEvidenceConflict).where(
            MultimodalEvidenceConflict.case_id == case_id,
            MultimodalEvidenceConflict.resolution_status == "OPEN",
            MultimodalEvidenceConflict.severity == "HIGH",
            MultimodalEvidenceConflict.resolution_required.is_(True),
        )))

    def list_evidence(self, case_id: str) -> list[MultimodalEvidenceItem]:
        return list(self.db.scalars(
            select(MultimodalEvidenceItem)
            .where(MultimodalEvidenceItem.case_id == case_id)
            .order_by(MultimodalEvidenceItem.created_at, MultimodalEvidenceItem.id)
        ))

    def get_agent_run(self, run_id: str) -> AgentRun | None:
        return self.db.scalar(select(AgentRun).where(AgentRun.run_id == run_id))

    def create_agent_run(self, item: AgentRun) -> AgentRun:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_artifact(self, artifact_id: UUID | None) -> AgentArtifact | None:
        return self.db.get(AgentArtifact, artifact_id) if artifact_id else None

    def latest_artifact(self, workflow_id: str, artifact_type: str) -> AgentArtifact | None:
        return self.db.scalar(
            select(AgentArtifact)
            .where(AgentArtifact.source_type == "maintenance_workflow")
            .where(AgentArtifact.source_id == workflow_id)
            .where(AgentArtifact.artifact_type == artifact_type)
            .order_by(AgentArtifact.created_at.desc())
        )

    def create_artifact(self, item: AgentArtifact) -> AgentArtifact:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def create_approval(self, item: AgentApproval) -> AgentApproval:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_approval_for_artifact(self, artifact: AgentArtifact, *, lock: bool = False) -> AgentApproval | None:
        statement = (
            select(AgentApproval)
            .where(AgentApproval.run_id == artifact.run_id)
            .where(AgentApproval.payload_json["artifact_id"].astext == str(artifact.id))
            .order_by(AgentApproval.created_at.desc())
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def save_approval(self, item: AgentApproval) -> AgentApproval:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_sop(self, sop_id: UUID | None) -> SOPTemplate | None:
        return self.db.get(SOPTemplate, sop_id) if sop_id else None

    def get_sop_execution(self, execution_id: UUID | None) -> SOPExecutionRecord | None:
        return self.db.get(SOPExecutionRecord, execution_id) if execution_id else None

    def get_task(self, task_id: UUID | None, *, lock: bool = False) -> MaintenanceTask | None:
        if not task_id:
            return None
        statement = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def save_task(self, item: MaintenanceTask) -> MaintenanceTask:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def create_step(self, item: MaintenanceTaskStepExecution) -> MaintenanceTaskStepExecution:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def save_step(self, item: MaintenanceTaskStepExecution) -> MaintenanceTaskStepExecution:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_step(self, workflow_id: str, step_id: UUID, *, lock: bool = False) -> MaintenanceTaskStepExecution | None:
        statement = select(MaintenanceTaskStepExecution).where(
            MaintenanceTaskStepExecution.workflow_id == workflow_id,
            MaintenanceTaskStepExecution.id == step_id,
        )
        if lock:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def list_steps(self, workflow_id: str) -> list[MaintenanceTaskStepExecution]:
        return list(self.db.scalars(
            select(MaintenanceTaskStepExecution)
            .where(MaintenanceTaskStepExecution.workflow_id == workflow_id)
            .order_by(MaintenanceTaskStepExecution.sequence)
        ))

    def create_execution_record(self, item: MaintenanceTaskExecutionRecord) -> MaintenanceTaskExecutionRecord:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_execution_record(self, record_id: UUID | None) -> MaintenanceTaskExecutionRecord | None:
        return self.db.get(MaintenanceTaskExecutionRecord, record_id) if record_id else None

    def list_execution_records(self, workflow_id: str) -> list[MaintenanceTaskExecutionRecord]:
        return list(self.db.scalars(
            select(MaintenanceTaskExecutionRecord)
            .where(MaintenanceTaskExecutionRecord.workflow_id == workflow_id)
            .order_by(MaintenanceTaskExecutionRecord.performed_at, MaintenanceTaskExecutionRecord.id)
        ))

    def get_media_items(self, media_ids: list[UUID]) -> list[UploadedMedia]:
        if not media_ids:
            return []
        return list(self.db.scalars(select(UploadedMedia).where(UploadedMedia.id.in_(media_ids))))

    def get_device_record_by_task(self, task_id: UUID) -> DeviceMaintenanceRecord | None:
        return self.db.scalar(
            select(DeviceMaintenanceRecord).where(DeviceMaintenanceRecord.task_id == task_id)
        )

    def create_correction(self, item: ModelOutputCorrection) -> ModelOutputCorrection:
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def get_correction(self, correction_id: UUID) -> ModelOutputCorrection | None:
        return self.db.get(ModelOutputCorrection, correction_id)

    def list_corrections(self, ids: list[UUID]) -> list[ModelOutputCorrection]:
        if not ids:
            return []
        return list(self.db.scalars(
            select(ModelOutputCorrection)
            .where(ModelOutputCorrection.id.in_(ids))
            .order_by(ModelOutputCorrection.created_at)
        ))

    def count_duplicate_formal_tasks(self) -> int:
        return int(self.db.scalar(
            select(func.count()).select_from(
                select(MaintenanceWorkflow.formal_task_id)
                .where(MaintenanceWorkflow.formal_task_id.is_not(None))
                .group_by(MaintenanceWorkflow.formal_task_id)
                .having(func.count(MaintenanceWorkflow.id) > 1)
                .subquery()
            )
        ) or 0)
