from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from tests.minimax_test_helpers import candidate, understanding


def test_deterministic_rerank_preserves_candidate_and_source_boundaries() -> None:
    items = [
        candidate("a", content="通信检查与处理步骤", rrf=0.4),
        candidate("b", content="普通说明", rrf=0.5),
    ]
    sources = {item.candidate_id: set(item.source_channels) for item in items}
    result = DeterministicEvidenceRerankService().rerank(items, understanding=understanding())
    assert {item.candidate_id for item in result.candidates} == {"a", "b"}
    assert all(item.source_channels == sources[item.candidate_id] for item in result.candidates)
    assert result.diagnostics["weights_sum"] == 1.0
