from app.services.dedicated_rerank_service import DedicatedRerankService
from tests.minimax_test_helpers import candidate, understanding
from tests.r5_r6_test_helpers import StaticRerankAdapter, qwen_settings


def test_dedicated_rerank_does_not_modify_source_locator_or_create_citations() -> None:
    item = candidate("a", content="来源证据", rrf=0.4)
    locator = dict(item.source_locator)
    result = DedicatedRerankService(qwen_settings(), adapter=StaticRerankAdapter([0])).rerank(
        [item], understanding=understanding(), allow_real_api=True
    )
    assert item.source_locator == locator
    assert result.candidates[0].source_locator == locator
    assert result.diagnostics["citation_modifications"] == 0
