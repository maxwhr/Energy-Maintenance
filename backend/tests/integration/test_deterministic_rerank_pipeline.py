from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from tests.minimax_test_helpers import candidate, understanding


def test_deterministic_rerank_pipeline_protects_exact_alarm_with_citation() -> None:
    u = understanding("告警 2031 如何处理")
    exact = candidate("exact", content="告警 2031 的处理步骤", rrf=0.1, exact_alarm=True)
    broad = candidate("broad", content="常见告警说明", rrf=0.8)
    result = DeterministicEvidenceRerankService().rerank(
        [broad, exact], understanding=u, citation_status={broad.chunk_id: True, exact.chunk_id: True}
    )
    assert result.candidates[0].candidate_id == "exact"
    assert "EXACT_ENTITY_VALID_CITATION_PROTECTED" in result.diagnostics["score_breakdown"]["exact"]["reason_codes"]
