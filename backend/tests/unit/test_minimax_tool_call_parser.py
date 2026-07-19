from app.services.model_adapters.minimax_anthropic_adapter import MiniMaxAnthropicAdapter


def test_parser_rejects_wrong_or_multiple_tools_and_flags_thinking() -> None:
    parsed = MiniMaxAnthropicAdapter.parse_tool_response({"content": [
        {"type": "thinking", "thinking": "must not be logged"},
        {"type": "tool_use", "name": "wrong", "input": {}},
    ]}, "required")
    assert parsed["error_code"] == "WRONG_TOOL"
    assert parsed["diagnostics"]["unexpected_thinking_block"] is True
    assert "must not be logged" not in str(parsed["diagnostics"])
