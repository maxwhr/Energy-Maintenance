from __future__ import annotations

from app.main import app
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService
from task25d_common import now_iso, write_json


def main() -> int:
    policy = MaintenanceWorkflowPolicyService
    paths = app.openapi()["paths"]
    required_paths = [path for path in paths if path.startswith("/api/maintenance-workflows")]
    checks = {
        "viewer_read_only": "viewer" not in policy.WRITE_ROLES,
        "engineer_can_execute": "engineer" in policy.TASK_EXECUTION_ROLES,
        "expert_high_risk_review": "expert" in policy.HIGH_RISK_REVIEW_ROLES,
        "admin_audited_management": "admin" in policy.WRITE_ROLES,
        "formal_task_roles_limited": policy.FORMAL_TASK_ROLES == {"engineer", "admin"},
        "workflow_openapi_paths": len(required_paths) >= 20,
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "rbac_checks": len(checks),
    }
    write_json("rbac.json", payload)
    print(payload["status"])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

