from app.services.retrieval_pilot_service import RetrievalPilotService


def test_engineer_cannot_write_expert_verified():
    assert "engineer" in RetrievalPilotService.allowed_review_roles(expert=False)
    assert "engineer" not in RetrievalPilotService.allowed_review_roles(expert=True)
    assert "viewer" not in RetrievalPilotService.allowed_review_roles(expert=False)
