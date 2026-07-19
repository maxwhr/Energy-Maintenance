from app.services.rrf_fusion_service import RRFFusionService
from tests.unit.test_rrf_fusion import candidate


def test_semantic_unit_identity_survives_fusion():
    item = candidate("su:unit-1", "SEMANTIC_UNIT"); item.semantic_unit_id = "unit-1"; item.source_chunk_ids = ["c1", "c2"]
    fused = RRFFusionService().fuse({"SEMANTIC_UNIT:ORIGINAL:0": [item]})
    assert fused[0].candidate_id == "su:unit-1" and fused[0].source_chunk_ids == ["c1", "c2"]
