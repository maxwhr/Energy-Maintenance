from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import (
    MaintenanceTaskExecutionRecord,
    MaintenanceTaskStepExecution,
    MaintenanceWorkflow,
    MaintenanceWorkflowEvent,
    ModelOutputCorrection,
)


class MaintenanceWorkflowStatusService:
    def __init__(self, db: Session):
        self.db = db

    def get_status(self) -> dict:
        total = self._count(MaintenanceWorkflow.id)
        events = self._count(MaintenanceWorkflowEvent.id)
        audited = int(self.db.scalar(
            select(func.count(distinct(MaintenanceWorkflowEvent.workflow_id)))
        ) or 0)
        duplicate_active_cases = int(self.db.scalar(
            select(func.count()).select_from(
                select(MaintenanceWorkflow.case_id)
                .where(MaintenanceWorkflow.status.in_({
                    "ACTIVE", "WAITING_USER", "WAITING_ENGINEER", "WAITING_EXPERT", "BLOCKED"
                }))
                .group_by(MaintenanceWorkflow.case_id)
                .having(func.count(MaintenanceWorkflow.id) > 1)
                .subquery()
            )
        ) or 0)
        duplicate_tasks = int(self.db.scalar(
            select(func.count()).select_from(
                select(MaintenanceWorkflow.formal_task_id)
                .where(MaintenanceWorkflow.formal_task_id.is_not(None))
                .group_by(MaintenanceWorkflow.formal_task_id)
                .having(func.count(MaintenanceWorkflow.id) > 1)
                .subquery()
            )
        ) or 0)
        correction_count = int(self.db.scalar(
            select(func.count(ModelOutputCorrection.id)).where(
                ModelOutputCorrection.source_type == "maintenance_workflow"
            )
        ) or 0)
        expert_auto_writes = int(self.db.scalar(
            select(func.count(ModelOutputCorrection.id)).where(
                ModelOutputCorrection.source_type == "maintenance_workflow",
                ModelOutputCorrection.metadata_json["expert_verified"].astext == "true",
            )
        ) or 0)
        return {
            "status": "READY" if duplicate_active_cases == 0 and duplicate_tasks == 0 else "QUALITY_GATE_FAILED",
            "workflows": total,
            "active": self._workflow_status_count("ACTIVE"),
            "completed": self._workflow_status_count("COMPLETED"),
            "blocked": self._workflow_status_count("BLOCKED"),
            "cancelled": self._workflow_status_count("CANCELLED"),
            "failed": self._workflow_status_count("FAILED"),
            "events": events,
            "audited_workflows": audited,
            "audit_coverage": round(audited / total, 6) if total else 1.0,
            "step_records": self._count(MaintenanceTaskStepExecution.id),
            "execution_records": self._count(MaintenanceTaskExecutionRecord.id),
            "correction_drafts": correction_count,
            "duplicate_active_workflows": duplicate_active_cases,
            "duplicate_formal_tasks": duplicate_tasks,
            "expert_verified_auto_writes": expert_auto_writes,
            "automatic_knowledge_updates": 0,
            "task25c_status": "MULTIMODAL_BENCHMARK_INSUFFICIENT",
            "qwen3_rerank_status": "DEFERRED_QWEN3_RERANK_CONFIG",
            "full_reindex_executed": False,
        }

    def _workflow_status_count(self, status: str) -> int:
        return int(self.db.scalar(
            select(func.count(MaintenanceWorkflow.id)).where(MaintenanceWorkflow.status == status)
        ) or 0)

    def _count(self, column) -> int:
        return int(self.db.scalar(select(func.count(column))) or 0)
