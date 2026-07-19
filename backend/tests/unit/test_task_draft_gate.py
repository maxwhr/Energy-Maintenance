from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_task_draft_requires_approved_sop_or_explicit_draft_only_preparation():
    assert not MaintenanceWorkflowPolicyService.can_create_task_draft(
        approved_sop=False, personal_preparation_confirmed=False
    ).allowed
    assert MaintenanceWorkflowPolicyService.can_create_task_draft(
        approved_sop=True, personal_preparation_confirmed=False
    ).allowed

