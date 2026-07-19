from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from tests.minimax_test_helpers import candidate, understanding


def test_intent_match_promotes_direct_cause_evidence() -> None:
    u = understanding("通信掉线是什么原因")
    cause = candidate("cause", content="可能原因：通信线缆松动导致离线", rrf=0.2)
    other = candidate("other", content="产品参数表", rrf=0.2)
    result = DeterministicEvidenceRerankService().rerank([other, cause], understanding=u)
    assert result.candidates[0].candidate_id == "cause"
    assert result.diagnostics["score_breakdown"]["cause"]["intent_match"] > 0
