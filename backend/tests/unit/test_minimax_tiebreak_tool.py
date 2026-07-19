from app.services.minimax_tiebreak_service import CandidateTieBreakPatch


def test_tiebreak_tool_schema_uses_only_bounded_candidate_aliases() -> None:
    schema = CandidateTieBreakPatch.model_json_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["ordered_candidate_ids"]["maxItems"] == 6
