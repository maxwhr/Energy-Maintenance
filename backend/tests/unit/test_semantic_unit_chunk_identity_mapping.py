from app.services.evidence_identity_service import EvidenceIdentityService
from tests.minimax_test_helpers import candidate


def test_unit_matches_any_direct_source_chunk():
    item = candidate("unit", content="告警原因和处理", rrf=.8)
    item.semantic_unit_id = "su-1"
    item.source_chunk_ids = ["chunk-a", "chunk-b"]
    EvidenceIdentityService().apply(item)
    assert EvidenceIdentityService.evaluation_match(item, {"chunk-b"})
