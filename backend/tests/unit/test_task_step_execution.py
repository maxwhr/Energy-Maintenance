from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_safety_step_cannot_be_skipped_and_prerequisites_are_enforced():
    skipped = MaintenanceWorkflowPolicyService.can_transition_step(
        current="PENDING",
        target="SKIPPED_WITH_REASON",
        is_safety_step=True,
        skip_reason="not applicable",
        prerequisites_satisfied=True,
    )
    assert not skipped.allowed
    blocked = MaintenanceWorkflowPolicyService.can_transition_step(
        current="PENDING",
        target="IN_PROGRESS",
        is_safety_step=False,
        skip_reason=None,
        prerequisites_satisfied=False,
    )
    assert not blocked.allowed

