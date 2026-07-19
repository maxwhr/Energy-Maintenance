from app.services.evidence_aware_rerank_service import EvidenceAwareRerankService
from tests.unit.test_evidence_rerank import candidates, understanding


def test_invalid_rerank_preserves_original_order():
    original = candidates()
    before = [item.candidate_id for item in original]
    result = EvidenceAwareRerankService(None, model_call=lambda _: "not-json").rerank(original, understanding=understanding(), allow_real_api=True, force=True)
    assert result.fallback and [item.candidate_id for item in result.candidates] == before
