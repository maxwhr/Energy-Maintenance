from app.schemas.query_understanding import QueryUnderstandingV2Patch


def test_query_understanding_v2_schema_is_flat_and_strict() -> None:
    schema = QueryUnderstandingV2Patch.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "intent", "canonical_query", "requested_information", "ambiguity",
        "missing_slots", "needs_clarification", "clarifying_question", "confidence",
    }
    assert set(schema["properties"]) == set(schema["required"])
    assert schema["properties"]["canonical_query"]["maxLength"] == 256
    assert schema["properties"]["requested_information"]["maxItems"] == 5
    assert schema["properties"]["missing_slots"]["maxItems"] == 4
