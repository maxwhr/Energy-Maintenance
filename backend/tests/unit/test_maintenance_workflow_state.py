import pytest

from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_workflow_state_allows_only_adjacent_business_transition():
    policy = MaintenanceWorkflowPolicyService()
    assert policy.can_transition_stage("DIAGNOSIS_REVIEW", "SOP_DRAFT").allowed
    decision = policy.can_transition_stage("DIAGNOSIS_REVIEW", "TASK_CREATED")
    assert not decision.allowed
    assert "illegal" in decision.reasons[0]

