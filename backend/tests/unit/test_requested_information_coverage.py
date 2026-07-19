from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService


def test_requested_information_coverage_is_set_based():
    supported = DeterministicEvidenceRerankService.requested_information_support(
        "可能原因是接线松动，检查并重新连接", ["CAUSE", "ACTION", "SAFETY"]
    )
    assert supported == {"CAUSE", "ACTION"}
