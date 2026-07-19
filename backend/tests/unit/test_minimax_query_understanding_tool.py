from app.schemas.query_understanding import LLMQueryUnderstandingPatch


def test_query_understanding_tool_schema_is_strict_bounded_and_required() -> None:
    schema = LLMQueryUnderstandingPatch.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["retrieval_queries"]["maxItems"] == 5
    assert schema["properties"]["ambiguity_options"]["maxItems"] == 5
