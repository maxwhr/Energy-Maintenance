from app.services.maintenance_workflow_policy_service import (
    MaintenanceWorkflowPolicyService,
    WORKFLOW_STAGE_ORDER,
)


def test_policy_defines_complete_closed_loop_and_viewer_is_read_only():
    assert WORKFLOW_STAGE_ORDER[0] == "CASE_ANALYSIS"
    assert WORKFLOW_STAGE_ORDER[-1] == "CLOSED"
    assert "viewer" not in MaintenanceWorkflowPolicyService.WRITE_ROLES

