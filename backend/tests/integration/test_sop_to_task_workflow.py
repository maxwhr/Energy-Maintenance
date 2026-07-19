from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_approved_sop_is_required_for_formal_task_even_when_draft_preparation_is_allowed():
    assert MaintenanceWorkflowPolicyService.can_create_task_draft(
        approved_sop=False, personal_preparation_confirmed=True
    ).allowed
    formal = MaintenanceWorkflowPolicyService.can_create_formal_task(
        actor_role="engineer", task_draft_valid=True, sop_approved=False,
        device_exists=True, safety_present=True, verification_present=True,
        citations_present=True, assignee_valid=True,
    )
    assert not formal.allowed

