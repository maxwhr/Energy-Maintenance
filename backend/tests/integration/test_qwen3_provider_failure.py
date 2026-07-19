from app.services.dedicated_rerank_service import DedicatedRerankService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_failure_does_not_call_other_model_or_change_fallback_order() -> None:
    source = [candidate(label, content="通信处理", rrf=0.2) for label in ("a", "b", "c")]
    fallback = [source[2], source[0], source[1]]
    result = DedicatedRerankService(
        qwen_settings(), adapter=StaticRerankAdapter(status="QWEN3_RERANK_PROVIDER_5XX")
    ).rerank(source, understanding=understanding(), allow_real_api=True, fallback_candidates=fallback)
    assert [item.candidate_id for item in result.candidates] == ["c", "a", "b"]
    assert result.diagnostics["provider"] == "dashscope"
    assert "minimax" not in str(result.diagnostics).lower()
    assert "stepfun" not in str(result.diagnostics).lower()
