import inspect

from app.services.evidence_aware_rerank_service import EvidenceAwareRerankService


def test_rerank_uses_shared_structured_service():
    source = inspect.getsource(EvidenceAwareRerankService.rerank)
    assert "self.structured.call" in source
    assert "RerankStructuredPayload" in source
