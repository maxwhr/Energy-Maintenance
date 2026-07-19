from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_case_evidence_contract_reaches_diagnosis_review_only_with_grounding():
    decision = MaintenanceWorkflowPolicyService.can_create_diagnosis(
        case_status="EVIDENCE_READY",
        has_input_evidence=True,
        evidence_has_locator=True,
        citation_count=1,
        open_high_conflicts=0,
        hypothesis_count=1,
    )
    assert decision.allowed

