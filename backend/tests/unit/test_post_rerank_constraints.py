from app.services.post_rerank_constraint_service import PostRerankConstraintService
from tests.minimax_test_helpers import candidate, understanding


def test_cause_and_action_are_present_in_top3_when_available() -> None:
    u = understanding("设备通信掉线，原因是什么，如何处理")
    u.requested_information = ["CAUSE", "ACTION"]
    items = [
        candidate("background", content="通信产品概述", rrf=0.9),
        candidate("other", content="一般说明", rrf=0.8),
        candidate("cause", content="可能原因是通信线缆松动", rrf=0.2),
        candidate("action", content="处理方法：检查并紧固通信线缆", rrf=0.1),
    ]
    result = PostRerankConstraintService().apply(items, understanding=u)
    top = {item.candidate_id for item in result.candidates[:3]}
    assert "cause" in top
    assert "action" in top
