from app.schemas.maintenance_workflow import DiagnosisConfirmationRequest
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_diagnosis_confirmation_requires_human_role_and_explicit_fields():
    payload = DiagnosisConfirmationRequest(
        idempotency_key="confirm-0001",
        action="ENGINEER_CONFIRM",
        confirmed_fields={"device_model": "SUN2000"},
    )
    assert payload.confirmed_fields
    assert MaintenanceWorkflowPolicyService.can_confirm_diagnosis(
        action=payload.action, actor_role="engineer", high_risk=False
    ).allowed
    assert not MaintenanceWorkflowPolicyService.can_confirm_diagnosis(
        action=payload.action, actor_role="viewer", high_risk=False
    ).allowed

