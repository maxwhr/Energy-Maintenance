from app.services.dedicated_rerank_service import DedicatedRerankService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_provider_indexes_map_to_original_candidates_and_append_unreturned() -> None:
    items = [candidate(label, content=f"处理步骤 {label}", rrf=0.3) for label in ("a", "b", "c")]
    result = DedicatedRerankService(
        qwen_settings(), adapter=StaticRerankAdapter([2, 0])
    ).rerank(items, understanding=understanding("通信异常如何处理"), allow_real_api=True)
    assert [item.candidate_id for item in result.candidates] == ["c", "a", "b"]
    assert result.diagnostics["candidate_additions"] == 0
    assert result.diagnostics["candidate_removals"] == 0
