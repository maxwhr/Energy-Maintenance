from app.schemas.query_understanding import QueryUnderstandingV2Patch


def test_v2_contract_rejects_nested_retrieval_queries() -> None:
    schema = QueryUnderstandingV2Patch.model_json_schema()
    assert "retrieval_queries" not in schema["properties"]
    assert "retrieval_hypotheses" not in schema["properties"]
    assert "secondary_intents" not in schema["properties"]
    assert "device_models" not in schema["properties"]
    assert "alarm_codes" not in schema["properties"]

