import asyncio

import httpx

from app.services.rerank_adapters.qwen3_rerank_adapter import Qwen3RerankAdapter
from tests.r5_r6_test_helpers import qwen_settings


def test_adapter_posts_expected_contract_and_sanitizes_response() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"request_id": "provider-secret-id", "results": [
            {"index": 1, "relevance_score": 0.9, "document": "must-not-be-trusted"},
            {"index": 0, "relevance_score": 0.4},
        ]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = Qwen3RerankAdapter(qwen_settings(), client=client)
    result = asyncio.run(adapter.rerank(
        query="通信故障原因", documents=["候选A", "候选B"], top_n=2,
        instruct="rank direct evidence", allow_real_api=True, request_id="local-id",
    ))
    asyncio.run(client.aclose())
    assert result.success is True
    assert [item.index for item in result.results] == [1, 0]
    assert result.request_id_hash != "provider-secret-id"
    assert captured["path"].endswith("/reranks")
    assert captured["authorization"] == "Bearer x"
    assert '"model":"qwen3-rerank"' in captured["body"]
