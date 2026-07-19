from app.services.retrieval_pilot_service import RetrievalPilotService


def test_empty_expert_pool_blocks_freeze_and_engineer_is_not_expert():
    ready, failures = RetrievalPilotService._readiness([])
    assert ready is False
    assert failures
    assert "engineer" not in RetrievalPilotService.allowed_review_roles(expert=True)
