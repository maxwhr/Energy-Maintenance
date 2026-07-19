from types import SimpleNamespace

from app.services.retrieval_pilot_service import RetrievalPilotService


def test_reconciliation_does_not_claim_external_counts_without_pilot_index():
    service = RetrievalPilotService.__new__(RetrievalPilotService)
    service.settings = SimpleNamespace(DASHVECTOR_PILOT_COLLECTION="pilot")
    service.db = SimpleNamespace(scalar=lambda statement: 0)
    result = service.reconcile_summary(allow_real_api=True)
    assert result["status"] == "BLOCKED_NO_PILOT_INDEX"
    assert result["dashvector_vectors"] is None
    assert result["external_api_called"] is False
