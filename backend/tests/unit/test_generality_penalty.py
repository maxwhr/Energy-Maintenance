from tests.minimax_test_helpers import candidate
from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService


def test_full_section_without_request_coverage_is_penalized():
    broad = candidate("broad", content="产品介绍" * 700, rrf=0.8)
    broad.source_query_types = {"FULL_SECTION"}
    specific = candidate("specific", content="检查通信线并重新连接", rrf=0.4)
    assert DeterministicEvidenceRerankService.generality_penalty(broad, 0.0) > DeterministicEvidenceRerankService.generality_penalty(specific, 1.0)
