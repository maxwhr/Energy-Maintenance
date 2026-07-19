from app.services.rrf_fusion_service import RRFFusionService
from tests.unit.test_rrf_fusion import candidate


def test_same_channel_query_variants_get_one_vote():
    service = RRFFusionService()
    result = service.fuse({"SCOPED_KEYWORD:ORIGINAL:0": [candidate("a", "SCOPED_KEYWORD")], "SCOPED_KEYWORD:CAUSE:1": [candidate("a", "SCOPED_KEYWORD")]})
    assert result and service.last_diagnostics["duplicate_votes_removed"] == 1
    assert len(service.last_diagnostics["vote_breakdown"]["a"]) == 1
