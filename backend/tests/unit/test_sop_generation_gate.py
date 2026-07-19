from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_sop_gate_requires_citation_safety_model_and_resolved_conflicts():
    denied = MaintenanceWorkflowPolicyService.can_create_sop(
        diagnosis_status="DRAFT",
        citation_count=0,
        safety_count=0,
        device_model_confirmed=False,
        open_high_conflicts=1,
        high_risk=False,
        expert_reviewed=False,
    )
    assert not denied.allowed
    assert len(denied.reasons) == 5
    assert MaintenanceWorkflowPolicyService.can_create_sop(
        diagnosis_status="ENGINEER_CONFIRMED",
        citation_count=1,
        safety_count=1,
        device_model_confirmed=True,
        open_high_conflicts=0,
        high_risk=False,
        expert_reviewed=False,
    ).allowed

