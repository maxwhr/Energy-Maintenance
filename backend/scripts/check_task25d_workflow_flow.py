from __future__ import annotations

from sqlalchemy import distinct, func, select

from app.core.database import SessionLocal
from app.models import Device, MaintenanceWorkflow, MaintenanceWorkflowEvent, MultimodalMaintenanceCase, User
from app.schemas.maintenance_workflow import MaintenanceWorkflowCreate
from app.services.maintenance_workflow_policy_service import WORKFLOW_STAGE_ORDER, MaintenanceWorkflowPolicyService
from app.services.maintenance_workflow_service import MaintenanceWorkflowService
from task25d_common import now_iso, write_json


TARGET_CASES = 18


def main() -> int:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.role == "admin", User.status == "active"))
        device = db.scalar(select(Device).where(Device.status.in_({"normal", "fault", "maintenance"})))
        cases = list(db.scalars(
            select(MultimodalMaintenanceCase).order_by(MultimodalMaintenanceCase.created_at).limit(TARGET_CASES)
        ))
        if not admin or not device or len(cases) < TARGET_CASES:
            raise SystemExit("Task25D requires admin, active device, and 18 persisted cases")
        service = MaintenanceWorkflowService(db)
        workflows = []
        replay_success = 0
        for case in cases:
            existing = db.scalar(
                select(MaintenanceWorkflow)
                .where(MaintenanceWorkflow.case_id == case.case_id)
                .order_by(MaintenanceWorkflow.created_at)
            )
            if existing:
                workflow = existing
            else:
                result = service.create(MaintenanceWorkflowCreate(
                    case_id=case.case_id,
                    device_id=device.id,
                    idempotency_key=f"task25d-flow-{case.case_id}",
                    reason="Task25D persisted-case workflow acceptance",
                ), admin)
                workflow = service.get(result["workflow_id"], admin)
            workflows.append(workflow)
            replay = service.create(MaintenanceWorkflowCreate(
                case_id=case.case_id,
                device_id=workflow.device_id,
                idempotency_key=workflow.idempotency_key,
                reason="Task25D idempotency replay",
            ), admin)
            replay_success += int(bool(replay.get("idempotent_replay")))

        ids = [item.workflow_id for item in workflows]
        audited = int(db.scalar(
            select(func.count(distinct(MaintenanceWorkflowEvent.workflow_id))).where(
                MaintenanceWorkflowEvent.workflow_id.in_(ids)
            )
        ) or 0)
        duplicate_active = int(db.scalar(
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
        invalid_checks = [
            not MaintenanceWorkflowPolicyService.can_transition_stage(item.current_stage, "CLOSED").allowed
            for item in workflows
            if item.current_stage not in {"TASK_COMPLETED", "CORRECTION_REVIEW", "CLOSED"}
        ]
        state_valid = sum(item.current_stage in WORKFLOW_STAGE_ORDER for item in workflows)
        metrics = {
            "target_cases": TARGET_CASES,
            "workflows": len(workflows),
            "case_to_workflow_success": round(len(workflows) / TARGET_CASES, 6),
            "workflow_state_validity": round(state_valid / len(workflows), 6),
            "invalid_transitions_blocked": round(sum(invalid_checks) / len(invalid_checks), 6) if invalid_checks else 1.0,
            "audit_coverage": round(audited / len(workflows), 6),
            "idempotency_success": round(replay_success / len(workflows), 6),
            "duplicate_active_workflows": duplicate_active,
        }
        passed = (
            metrics["case_to_workflow_success"] == 1.0
            and metrics["workflow_state_validity"] == 1.0
            and metrics["invalid_transitions_blocked"] == 1.0
            and metrics["audit_coverage"] == 1.0
            and metrics["idempotency_success"] == 1.0
            and duplicate_active == 0
        )
        payload = {
            "generated_at": now_iso(),
            "status": "PASS" if passed else "FAIL",
            "metrics": metrics,
            "workflow_ids": ids,
            "case_ids": [item.case_id for item in workflows],
            "automatic_transitions": False,
        }
    write_json("workflow_flow.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

