from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_completion_requires_steps_safety_verification_measurement_and_media():
    complete = MaintenanceWorkflowPolicyService.can_verify_completion(
        required_steps_complete=True,
        safety_steps_complete=True,
        verification_steps_complete=True,
        unresolved_safety_events=0,
        required_measurements_present=True,
        required_media_present=True,
    )
    assert complete.allowed
    unsafe = MaintenanceWorkflowPolicyService.can_verify_completion(
        required_steps_complete=True,
        safety_steps_complete=True,
        verification_steps_complete=True,
        unresolved_safety_events=1,
        required_measurements_present=True,
        required_media_present=True,
    )
    assert not unsafe.allowed

