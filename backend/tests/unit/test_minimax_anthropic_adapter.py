import asyncio

import httpx

from app.schemas.model_gateway import ModelMessage
from app.services.model_adapters.base import ModelAdapterRequest
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter
from tests.minimax_test_helpers import minimax_settings


def test_minimax_adapter_parses_realistic_tool_block_without_exposing_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json={
            "id": "provider-id", "stop_reason": "tool_use",
            "content": [{"type": "tool_use", "id": "tool-id", "name": "submit", "input": {"ok": True}}],
            "usage": {"input_tokens": 3, "output_tokens": 4},
        })

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = MiniMaxAnthropicAdapter(minimax_settings(), client=client)
    request = ModelAdapterRequest(
        prompt="", messages=[ModelMessage(role="user", content="test")], model="MiniMax-M3",
        required_tool_name="submit", tools=[{"name": "submit", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "submit"}, thinking={"type": "disabled"}, service_tier="standard",
    )
    result = asyncio.run(adapter.achat(request))
    asyncio.run(client.aclose())
    assert result.success is True
    assert result.structured_payload == {"ok": True}
    assert "provider-id" not in str(result.raw_payload)
