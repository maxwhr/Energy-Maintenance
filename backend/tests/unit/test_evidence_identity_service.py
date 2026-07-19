from tests.minimax_test_helpers import candidate
from app.services.evidence_identity_service import EvidenceIdentityService


def test_semantic_and_source_chunk_share_alias_identity():
    item = candidate("x", content="处理步骤", rrf=0.5)
    item.semantic_unit_id = "unit-1"
    identity = EvidenceIdentityService().apply(item)
    assert identity.primary_id == "unit-1"
    assert item.chunk_id in identity.aliases
    assert EvidenceIdentityService.evaluation_match(item, {item.chunk_id})
