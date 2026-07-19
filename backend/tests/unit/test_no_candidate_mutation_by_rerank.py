from app.services.dedicated_rerank_service import DedicatedRerankService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_dedicated_rerank_does_not_mutate_input_candidate_body_or_source() -> None:
    items = [candidate("a", content="原始证据A", rrf=0.4), candidate("b", content="原始证据B", rrf=0.3)]
    before = [(item.content, set(item.source_channels), list(item.source_chunk_ids), dict(item.source_locator)) for item in items]
    DedicatedRerankService(qwen_settings(), adapter=StaticRerankAdapter([1, 0])).rerank(
        items, understanding=understanding(), allow_real_api=True
    )
    after = [(item.content, set(item.source_channels), list(item.source_chunk_ids), dict(item.source_locator)) for item in items]
    assert after == before
