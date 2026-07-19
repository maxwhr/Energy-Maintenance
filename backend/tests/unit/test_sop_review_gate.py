from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_high_risk_sop_requires_expert_or_admin():
    assert not MaintenanceWorkflowPolicyService.can_review_sop(
        actor_role="engineer", high_risk=True
    ).allowed
    assert MaintenanceWorkflowPolicyService.can_review_sop(
        actor_role="expert", high_risk=True
    ).allowed

