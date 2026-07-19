from app.services.rrf_fusion_service import RRFFusionService
from tests.unit.test_rrf_fusion import candidate


def test_multi_query_cannot_multiply_one_physical_channel():
    service = RRFFusionService()
    service.fuse({"SCOPED_KEYWORD:ORIGINAL:0": [candidate("a", "SCOPED_KEYWORD")], "SCOPED_KEYWORD:CAUSE:1": [candidate("a", "SCOPED_KEYWORD")], "RAW_VECTOR:ORIGINAL:2": [candidate("a", "RAW_VECTOR")]})
    assert len(service.last_diagnostics["vote_breakdown"]["a"]) == 2
