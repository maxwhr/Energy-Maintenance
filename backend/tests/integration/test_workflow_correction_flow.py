from app.schemas.maintenance_workflow import WorkflowCorrectionCandidateRequest


def test_correction_contract_is_a_draft_with_evidence_not_a_knowledge_write():
    payload = WorkflowCorrectionCandidateRequest(
        idempotency_key="correct-0002",
        candidate_type="SOP_INCOMPLETE",
        proposed_change={"add_step": "verify connector torque"},
        reason="execution record exposed a missing verification step",
        evidence_ids=["wfr_1"],
    )
    assert payload.evidence_ids == ["wfr_1"]
    assert "expert_verified" not in payload.model_dump()

