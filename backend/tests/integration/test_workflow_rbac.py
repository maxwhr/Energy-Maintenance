from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_workflow_rbac_matrix_has_no_viewer_write_or_expert_formal_task_bypass():
    policy = MaintenanceWorkflowPolicyService
    assert "viewer" not in policy.WRITE_ROLES
    assert policy.FORMAL_TASK_ROLES == {"engineer", "admin"}
    assert policy.HIGH_RISK_REVIEW_ROLES == {"expert", "admin"}

