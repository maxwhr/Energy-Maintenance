from app.services.dedicated_rerank_service import DedicatedRerankService
from app.services.post_rerank_constraint_service import PostRerankConstraintService
from app.services.pre_rerank_hard_guard_service import PreRerankHardGuardService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_qwen_pipeline_preserves_boundary_through_guards() -> None:
    u = understanding("通信掉线的原因和处理方法")
    u.requested_information = ["CAUSE", "ACTION"]
    items = [
        candidate("background", content="通信产品概述", rrf=0.8),
        candidate("cause", content="可能原因是通信线松动", rrf=0.3),
        candidate("action", content="处理方法：检查通信线并紧固", rrf=0.2),
    ]
    guarded = PreRerankHardGuardService().apply(items, understanding=u)
    reranked = DedicatedRerankService(qwen_settings(), adapter=StaticRerankAdapter([1, 2, 0])).rerank(
        guarded.candidates, understanding=u, allow_real_api=True
    )
    constrained = PostRerankConstraintService().apply(reranked.candidates, understanding=u)
    assert {item.candidate_id for item in constrained.candidates} == {"background", "cause", "action"}
    assert {item.candidate_id for item in constrained.candidates[:3]} >= {"cause", "action"}
    assert reranked.diagnostics["source_modifications"] == 0
