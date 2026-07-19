import pytest
from pydantic import ValidationError

from app.schemas.maintenance_workflow import WorkflowCorrectionCandidateRequest
from app.services.maintenance_workflow_policy_service import MaintenanceWorkflowPolicyService


def test_correction_candidate_requires_traceable_evidence_and_defaults_are_not_approval():
    assert not MaintenanceWorkflowPolicyService.can_create_correction(
        task_completed=True, evidence_count=0
    ).allowed
    with pytest.raises(ValidationError):
        WorkflowCorrectionCandidateRequest(
            idempotency_key="correct-0001",
            candidate_type="ACTION_MISMATCH",
            proposed_change={"action": "inspect connector"},
            reason="field finding",
            evidence_ids=[],
        )

