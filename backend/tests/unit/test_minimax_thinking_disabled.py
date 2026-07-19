from app.schemas.model_gateway import ModelMessage
from app.services.model_adapters.base import ModelAdapterRequest
from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter
from tests.minimax_test_helpers import minimax_settings


def test_thinking_is_always_explicitly_disabled() -> None:
    adapter = MiniMaxAnthropicAdapter(minimax_settings())
    payload = adapter._payload(ModelAdapterRequest(
        prompt="", messages=[ModelMessage(role="user", content="x")], required_tool_name="submit",
        tools=[{"name": "submit", "input_schema": {}}], thinking={"type": "disabled"},
    ))
    assert payload["thinking"] == {"type": "disabled"}
