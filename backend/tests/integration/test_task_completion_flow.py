from app.schemas.maintenance_workflow import WorkflowTaskVerificationRequest
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_verification_request_and_stage_transition_are_explicit():
    request = WorkflowTaskVerificationRequest(
        idempotency_key="verify-0001",
        outcome="VERIFIED_SUCCESS",
        verification_summary="device returned to normal",
        required_measurements_present=True,
        required_media_present=True,
    )
    assert request.outcome == "VERIFIED_SUCCESS"
    assert MaintenanceWorkflowPolicyService.can_transition_stage(
        "TASK_EXECUTION", "RESULT_VERIFICATION"
    ).allowed

