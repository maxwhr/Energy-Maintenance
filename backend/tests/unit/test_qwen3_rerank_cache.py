import asyncio

import httpx

from app.services.rerank_adapters.qwen3_rerank_adapter import Qwen3RerankAdapter
from tests.r5_r6_test_helpers import qwen_settings


def test_only_successful_results_are_cached_by_hash_contract() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"results": [{"index": 0, "relevance_score": 0.8}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = Qwen3RerankAdapter(qwen_settings(), client=client)
    kwargs = dict(query="原因", documents=["直接原因"], top_n=1, instruct="rank", allow_real_api=True)
    first = asyncio.run(adapter.rerank(**kwargs))
    second = asyncio.run(adapter.rerank(**kwargs))
    asyncio.run(client.aclose())
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert calls == 1
