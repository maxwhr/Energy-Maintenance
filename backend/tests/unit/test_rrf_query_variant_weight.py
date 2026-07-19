from app.services.rrf_fusion_service import RRFFusionService
from tests.unit.test_rrf_fusion import candidate


def test_query_variant_weights_change_best_channel_vote():
    service = RRFFusionService()
    service.fuse({"SCOPED_KEYWORD:ORIGINAL:0": [candidate("a", "SCOPED_KEYWORD")], "SCOPED_KEYWORD:CAUSE:1": [candidate("a", "SCOPED_KEYWORD")]}, query_weights={"ORIGINAL": 1.0, "CAUSE": 0.1})
    vote = service.last_diagnostics["vote_breakdown"]["a"]["SCOPED_KEYWORD"]
    assert "ORIGINAL" in vote["vote_key"]
