from app.services.evidence_identity_service import EvidenceIdentityService
from app.services.rrf_fusion_service import RRFFusionService
from tests.minimax_test_helpers import candidate


def test_chunk_and_semantic_unit_do_not_occupy_two_fused_slots():
    chunk = candidate("chunk", content="同一事实", rrf=.8, channel="SCOPED_KEYWORD")
    unit = candidate("unit", content="同一事实", rrf=.7, channel="SEMANTIC_UNIT")
    unit.chunk_id = chunk.chunk_id
    unit.source_chunk_ids = [chunk.chunk_id]
    unit.semantic_unit_id = "su-1"
    EvidenceIdentityService().apply(chunk)
    EvidenceIdentityService().apply(unit)
    fused = RRFFusionService().fuse({"SCOPED_KEYWORD:ORIGINAL:0": [chunk], "SEMANTIC_UNIT:ORIGINAL:1": [unit]})
    assert len(fused) == 1
    assert {"SCOPED_KEYWORD", "SEMANTIC_UNIT"} <= fused[0].source_channels
