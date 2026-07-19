from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_formal_task_gate_rejects_unapproved_sop_and_automatic_roles():
    allowed = MaintenanceWorkflowPolicyService.can_create_formal_task(
        actor_role="engineer",
        task_draft_valid=True,
        sop_approved=True,
        device_exists=True,
        safety_present=True,
        verification_present=True,
        citations_present=True,
        assignee_valid=True,
    )
    assert allowed.allowed
    denied = MaintenanceWorkflowPolicyService.can_create_formal_task(
        actor_role="expert",
        task_draft_valid=True,
        sop_approved=False,
        device_exists=True,
        safety_present=True,
        verification_present=True,
        citations_present=True,
        assignee_valid=True,
    )
    assert not denied.allowed

