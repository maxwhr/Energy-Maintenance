import pytest

from app.services.structured_model_call_service import extract_json_payload


@pytest.mark.parametrize(("text", "strategy"), [("{\"a\":1}", "DIRECT_JSON"), ("```json\n{\"a\":1}\n```", "CODE_FENCE_JSON"), ("note {\"a\":1} end", "FIRST_JSON_OBJECT"), ("\ufeff  {\"a\":1}", "DIRECT_JSON")])
def test_extract_json_payload_shapes(text, strategy):
    payload, used = extract_json_payload(text)
    assert payload == {"a": 1} and used == strategy
