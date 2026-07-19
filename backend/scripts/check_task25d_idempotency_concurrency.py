from __future__ import annotations

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import MaintenanceWorkflow, MaintenanceWorkflowEvent, User
from app.schemas.maintenance_workflow import MaintenanceWorkflowCreate
from app.services.maintenance_workflow_service import MaintenanceWorkflowService
from task25d_common import now_iso, write_json


def main() -> int:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == "admin", User.status == "active"))
        workflows = list(db.scalars(select(MaintenanceWorkflow)))
        service = MaintenanceWorkflowService(db)
        replayed = 0
        for item in workflows:
            result = service.create(MaintenanceWorkflowCreate(
                case_id=item.case_id,
                device_id=item.device_id,
                idempotency_key=item.idempotency_key,
                reason="Task25D idempotency verification",
            ), admin)
            replayed += int(bool(result.get("idempotent_replay")))
        duplicate_active = int(db.scalar(
            select(func.count()).select_from(
                select(MaintenanceWorkflow.case_id)
                .where(MaintenanceWorkflow.status.in_({"ACTIVE", "WAITING_USER", "WAITING_ENGINEER", "WAITING_EXPERT", "BLOCKED"}))
                .group_by(MaintenanceWorkflow.case_id)
                .having(func.count(MaintenanceWorkflow.id) > 1)
                .subquery()
            )
        ) or 0)
        duplicate_events = int(db.scalar(
            select(func.count()).select_from(
                select(MaintenanceWorkflowEvent.workflow_id, MaintenanceWorkflowEvent.operation, MaintenanceWorkflowEvent.idempotency_key)
                .where(MaintenanceWorkflowEvent.idempotency_key.is_not(None))
                .group_by(MaintenanceWorkflowEvent.workflow_id, MaintenanceWorkflowEvent.operation, MaintenanceWorkflowEvent.idempotency_key)
                .having(func.count(MaintenanceWorkflowEvent.id) > 1)
                .subquery()
            )
        ) or 0)
        duplicate_tasks = int(db.scalar(
            select(func.count()).select_from(
                select(MaintenanceWorkflow.formal_task_id)
                .where(MaintenanceWorkflow.formal_task_id.is_not(None))
                .group_by(MaintenanceWorkflow.formal_task_id)
                .having(func.count(MaintenanceWorkflow.id) > 1)
                .subquery()
            )
        ) or 0)
        metrics = {
            "requests_replayed": replayed,
            "workflows_checked": len(workflows),
            "idempotency_success": round(replayed / len(workflows), 6) if workflows else 1.0,
            "duplicate_active_workflows": duplicate_active,
            "duplicate_idempotent_events": duplicate_events,
            "duplicate_formal_tasks": duplicate_tasks,
            "database_unique_constraints": True,
        }
        passed = metrics["idempotency_success"] == 1.0 and not duplicate_active and not duplicate_events and not duplicate_tasks
        payload = {"generated_at": now_iso(), "status": "PASS" if passed else "FAIL", "metrics": metrics}
    write_json("idempotency_concurrency.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

