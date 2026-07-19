from app.services.dedicated_rerank_service import DedicatedRerankService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_provider_failure_preserves_deterministic_fallback_order() -> None:
    source = [candidate(label, content="检查通信线缆", rrf=0.2) for label in ("a", "b")]
    fallback = [source[1], source[0]]
    result = DedicatedRerankService(
        qwen_settings(), adapter=StaticRerankAdapter(status="QWEN3_RERANK_TIMEOUT")
    ).rerank(source, understanding=understanding(), allow_real_api=True, fallback_candidates=fallback)
    assert [item.candidate_id for item in result.candidates] == ["b", "a"]
    assert result.diagnostics["fallback"] is True
    assert result.diagnostics["fallback_reason"] == "QWEN3_RERANK_TIMEOUT"
