from uuid import uuid4

from app.services.retrieval_pilot_service import RetrievalPilotService


def test_pilot_rollback_restores_base_route_without_changing_default_snapshot():
    metadata = {"session_status": "active", "config_snapshot": {"default_strategy": "keyword"}}
    result = RetrievalPilotService.rollback_metadata(metadata, user_id=uuid4(), reason="controlled drill")
    assert result["session_status"] == "rolled_back"
    assert result["base_route_restored"] is True
    assert result["config_snapshot"]["default_strategy"] == "keyword"
