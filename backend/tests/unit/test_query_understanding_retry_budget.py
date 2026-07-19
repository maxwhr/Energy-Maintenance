import asyncio

import httpx

from app.services.model_adapters.base import ModelAdapterRequest
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter
from tests.minimax_test_helpers import minimax_settings


def test_non_retryable_provider_failure_stays_within_single_request_budget() -> None:
    calls = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, json={"error": "server"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    settings = minimax_settings(MINIMAX_MAX_RETRIES=1)
    adapter = MiniMaxAnthropicAdapter(settings, client=client)
    response = asyncio.run(adapter.achat(ModelAdapterRequest(
        prompt="",
        messages=[],
        model="MiniMax-M3",
        required_tool_name="submit_query_understanding_v2",
        tools=[{"name": "submit_query_understanding_v2", "input_schema": {"type": "object"}}],
        timeout_seconds=4,
        service_tier="standard",
        allow_retry=True,
    )))
    asyncio.run(client.aclose())
    assert response.success is False
    assert response.error_code == "HTTP_500"
    assert len(calls) == 1

