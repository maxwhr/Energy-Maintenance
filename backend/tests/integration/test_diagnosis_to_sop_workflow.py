from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_confirmed_grounded_diagnosis_can_enter_sop_draft_gate():
    assert MaintenanceWorkflowPolicyService.can_transition_stage(
        "DIAGNOSIS_REVIEW", "SOP_DRAFT"
    ).allowed
    assert MaintenanceWorkflowPolicyService.can_create_sop(
        diagnosis_status="ENGINEER_CONFIRMED",
        citation_count=2,
        safety_count=1,
        device_model_confirmed=True,
        open_high_conflicts=0,
        high_risk=False,
        expert_reviewed=False,
    ).allowed

