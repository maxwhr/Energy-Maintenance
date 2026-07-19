from app.services.dedicated_rerank_service import DedicatedRerankService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_provider_direct_answer_becomes_rank_one() -> None:
    items = [
        candidate("background", content="通信背景介绍", rrf=0.9),
        candidate("direct", content="原因是RS485线松动，处理时断电后重新紧固并确认通信恢复", rrf=0.2),
    ]
    result = DedicatedRerankService(qwen_settings(), adapter=StaticRerankAdapter([1, 0])).rerank(
        items, understanding=understanding("通信掉线原因和处理"), allow_real_api=True
    )
    assert result.candidates[0].candidate_id == "direct"
    assert result.diagnostics["success"] is True
