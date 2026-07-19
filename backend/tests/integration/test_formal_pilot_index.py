from types import SimpleNamespace

from app.services.retrieval_pilot_service import RetrievalPilotService


def test_formal_pilot_index_requires_all_explicit_gates_and_isolated_collection():
    service = RetrievalPilotService.__new__(RetrievalPilotService)
    service.settings = SimpleNamespace(
        TASK25B_R2_PILOT_ENABLED=True, TASK25B_R2_ALLOW_PILOT_INDEX=True,
        TASK25B_ALLOW_REAL_API=True, DASHVECTOR_PILOT_COLLECTION="pilot",
        DASHVECTOR_PHYSICAL_COLLECTION="base",
    )
    result = service.pilot_index_preflight(allow_real_api=True, pilot_only=True, approved_only=True)
    assert result["accepted"] is True
    assert result["full_reindex_executed"] is False
