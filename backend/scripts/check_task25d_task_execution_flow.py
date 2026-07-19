from __future__ import annotations

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import MaintenanceTask, MaintenanceTaskExecutionRecord, MaintenanceTaskStepExecution, MaintenanceWorkflow
from task25d_common import now_iso, write_json


def main() -> int:
    with SessionLocal() as db:
        workflows = list(db.scalars(select(MaintenanceWorkflow)))
        task_workflows = [item for item in workflows if item.formal_task_id]
        tasks = list(db.scalars(select(MaintenanceTask).where(
            MaintenanceTask.id.in_([item.formal_task_id for item in task_workflows])
        ))) if task_workflows else []
        steps = list(db.scalars(select(MaintenanceTaskStepExecution)))
        records = list(db.scalars(select(MaintenanceTaskExecutionRecord)))
        record_counts = {kind: sum(item.record_type == kind for item in records) for kind in {
            "START", "PAUSE", "RESUME", "STEP_RESULT", "MEASUREMENT", "PHOTO", "PART_REPLACEMENT",
            "SAFETY_EVENT", "NEW_FINDING", "VERIFICATION", "COMPLETION_REQUEST", "EXPERT_ASSISTANCE",
        }}
        verification_task_ids = {item.task_id for item in records if item.record_type == "VERIFICATION"}
        completion_without_verification = sum(
            task.status == "completed" and task.id not in verification_task_ids for task in tasks
        )
        unsafe_skips = sum(item.is_safety_step and item.status == "SKIPPED_WITH_REASON" for item in steps)
        tasks_without_sop = sum(not item.approved_sop_id for item in task_workflows)
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
            "task_drafts": int(db.scalar(select(func.count()).select_from(MaintenanceWorkflow).where(MaintenanceWorkflow.task_draft_id.is_not(None))) or 0),
            "formal_tasks": len(tasks),
            "automatic_formal_tasks": sum(bool((item.metadata_json or {}).get("automatic_formal_task_creation")) for item in task_workflows),
            "started": sum(item.status in {"in_progress", "paused", "completed"} for item in tasks),
            "paused": sum(item.status == "paused" for item in tasks),
            "completed": sum(item.status == "completed" for item in tasks),
            "duplicate_tasks": duplicate_tasks,
            "tasks_without_approved_sop": tasks_without_sop,
            "step_records": len(steps),
            "unsafe_skips": unsafe_skips,
            "completion_without_verification": completion_without_verification,
            "record_types": record_counts,
            "measurements": sum(bool(item.measurements) for item in records),
            "media_records": sum(bool(item.media_ids) for item in records),
            "parts_replaced": sum(len(item.parts_replaced or []) for item in records),
            "timeline_coverage": 1.0 if task_workflows and records else 0.0,
        }
        passed = (
            metrics["automatic_formal_tasks"] == 0
            and duplicate_tasks == 0
            and tasks_without_sop == 0
            and unsafe_skips == 0
            and completion_without_verification == 0
            and metrics["formal_tasks"] >= 1
            and metrics["measurements"] >= 1
            and metrics["media_records"] >= 1
        )
        payload = {"generated_at": now_iso(), "status": "PASS" if passed else "FAIL", "metrics": metrics}
    write_json("task_execution_flow.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

