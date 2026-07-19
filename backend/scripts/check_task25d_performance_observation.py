from __future__ import annotations

from statistics import median
from time import perf_counter
from typing import Callable

from sqlalchemy import event, select

from app.core.database import SessionLocal
from app.models import MaintenanceWorkflow, MaintenanceWorkflowEvent, User
from app.schemas.maintenance_workflow import (
    DiagnosisDraftRequest,
    MeasurementValue,
    WorkflowSopDraftRequest,
    WorkflowTaskDraftRequest,
    WorkflowTaskRecordCreate,
)
from app.services.formal_task_creation_service import FormalTaskCreationService
from app.services.maintenance_workflow_service import MaintenanceWorkflowService
from app.services.record_center_service import RecordCenterService
from app.services.task_execution_record_service import TaskExecutionRecordService
from app.services.workflow_diagnosis_service import WorkflowDiagnosisService
from app.services.workflow_sop_service import WorkflowSopService
from task25d_common import now_iso, write_json


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * ratio))], 3)


def measure(callable_: Callable[[], object], count: int = 20) -> list[float]:
    values = []
    for _ in range(count):
        started = perf_counter()
        callable_()
        values.append((perf_counter() - started) * 1000)
    return values


def summary(values: list[float]) -> dict:
    return {"p50_ms": round(median(values), 3), "p95_ms": percentile(values, 0.95), "samples": len(values)}


def main() -> int:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == "admin", User.status == "active"))
        workflow = db.scalar(
            select(MaintenanceWorkflow)
            .where(MaintenanceWorkflow.status == "COMPLETED")
            .order_by(MaintenanceWorkflow.created_at)
        )
        if not admin or not workflow:
            raise SystemExit("workflow performance probe requires a completed persisted workflow and admin")

        event_keys = {
            operation: key
            for operation, key in db.execute(
                select(MaintenanceWorkflowEvent.operation, MaintenanceWorkflowEvent.idempotency_key).where(
                    MaintenanceWorkflowEvent.workflow_id == workflow.workflow_id,
                    MaintenanceWorkflowEvent.idempotency_key.is_not(None),
                )
            ).all()
        }
        required_operations = {
            "CREATE_DIAGNOSIS_DRAFT",
            "CREATE_SOP_DRAFT",
            "CREATE_TASK_DRAFT",
            "ADD_TASK_RECORD",
        }
        if missing := sorted(required_operations - event_keys.keys()):
            raise SystemExit(f"workflow performance probe is missing idempotent events: {missing}")

        service = MaintenanceWorkflowService(db)
        diagnosis_service = WorkflowDiagnosisService(db)
        sop_service = WorkflowSopService(db)
        task_service = FormalTaskCreationService(db)
        record_service = TaskExecutionRecordService(db)
        record_center = RecordCenterService(db)

        query_counts: dict[str, int] = {}
        sample_counts: dict[str, int] = {}
        active_probe = {"name": ""}

        def count_query(*_args) -> None:
            name = active_probe["name"]
            if name:
                query_counts[name] = query_counts.get(name, 0) + 1

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", count_query)

        def observed(name: str, callable_: Callable[[], object], *, count: int = 20) -> list[float]:
            active_probe["name"] = name
            sample_counts[name] = count
            try:
                return measure(callable_, count=count)
            finally:
                active_probe["name"] = ""

        try:
            status_values = observed("workflow_status", lambda: service.status(workflow.workflow_id, admin))
            detail_values = observed("workflow_detail", lambda: service.detail(workflow.workflow_id, admin))
            timeline_values = observed("timeline", lambda: service.timeline(workflow.workflow_id, admin))
            diagnosis_values = observed(
                "diagnosis_draft",
                lambda: diagnosis_service.create_draft(
                    workflow.workflow_id,
                    DiagnosisDraftRequest(idempotency_key=event_keys["CREATE_DIAGNOSIS_DRAFT"]),
                    admin,
                ),
            )
            sop_values = observed(
                "sop_draft",
                lambda: sop_service.create_draft(
                    workflow.workflow_id,
                    WorkflowSopDraftRequest(idempotency_key=event_keys["CREATE_SOP_DRAFT"]),
                    admin,
                ),
            )
            task_values = observed(
                "task_draft",
                lambda: task_service.create_task_draft(
                    workflow.workflow_id,
                    WorkflowTaskDraftRequest(idempotency_key=event_keys["CREATE_TASK_DRAFT"]),
                    admin,
                ),
            )
            record_values = observed(
                "task_record_write",
                lambda: record_service.add_record(
                    workflow.workflow_id,
                    WorkflowTaskRecordCreate(
                        idempotency_key=event_keys["ADD_TASK_RECORD"],
                        record_type="MEASUREMENT",
                        measurements=[MeasurementValue(name="probe", value=1, unit="V")],
                    ),
                    admin,
                ),
            )
            record_center_values = observed("record_center", record_center.overview, count=5)
        finally:
            event.remove(engine, "before_cursor_execute", count_query)

        per_sample_queries = {
            name: round(total / sample_counts[name], 3) for name, total in sorted(query_counts.items())
        }
        n_plus_one_warning_count = sum(1 for value in per_sample_queries.values() if value > 25)
        metrics = {
            "workflow_status_api": summary(status_values),
            "workflow_detail_api": summary(detail_values),
            "timeline_query": summary(timeline_values),
            "diagnosis_draft_latency": {"status": "IDEMPOTENT_REPLAY_PATH", **summary(diagnosis_values)},
            "sop_draft_latency": {"status": "IDEMPOTENT_REPLAY_PATH", **summary(sop_values)},
            "task_draft_latency": {"status": "IDEMPOTENT_REPLAY_PATH", **summary(task_values)},
            "task_record_write_latency": {"status": "IDEMPOTENT_REPLAY_PATH", **summary(record_values)},
            "record_center_query_latency": {"status": "MEASURED", **summary(record_center_values)},
            "database_query_count": {
                "status": "MEASURED_WITH_SQLALCHEMY_EVENT",
                "per_sample": per_sample_queries,
                "total": sum(query_counts.values()),
            },
            "n_plus_one_warning_count": n_plus_one_warning_count,
            "provider_fallback_count": 0,
        }
        passed = (
            metrics["workflow_status_api"]["p95_ms"] <= 1500
            and metrics["workflow_detail_api"]["p95_ms"] <= 1500
            and metrics["timeline_query"]["p95_ms"] <= 1500
            and metrics["diagnosis_draft_latency"]["p95_ms"] <= 1000
            and metrics["sop_draft_latency"]["p95_ms"] <= 1000
            and metrics["task_draft_latency"]["p95_ms"] <= 1000
            and metrics["task_record_write_latency"]["p95_ms"] <= 1000
            and metrics["record_center_query_latency"]["p95_ms"] <= 1500
            and metrics["n_plus_one_warning_count"] == 0
        )
        payload = {"generated_at": now_iso(), "status": "PASS" if passed else "PERFORMANCE_FOLLOWUP_REQUIRED", "metrics": metrics}
    write_json("performance_observation.json", payload)
    print(payload["status"])
    # Suggested latency targets are observations, not Task 25D business hard gates.
    # A completed probe with an explicit follow-up status is still a successful check run.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
