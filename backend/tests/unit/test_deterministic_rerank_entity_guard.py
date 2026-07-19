from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from tests.minimax_test_helpers import candidate, understanding


def test_no_model_query_does_not_bias_exact_model_candidates() -> None:
    u = understanding("通信为什么掉线")
    items = [
        candidate("model", content="SUN2000 通信", rrf=0.3, exact_model=True),
        candidate("generic", content="通信原因检查", rrf=0.3),
    ]
    result = DeterministicEvidenceRerankService().rerank(items, understanding=u)
    row = result.diagnostics["score_breakdown"]["model"]
    assert row["exact_model_match"] == 0.0
    assert row["conflict_penalty"] == 0.0
