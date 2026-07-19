from pydantic import ValidationError
import pytest

from app.schemas.query_understanding import MiniMaxAmbiguityPatch


def test_tool_schema_contains_only_four_allowed_fields():
    schema = MiniMaxAmbiguityPatch.model_json_schema()
    assert set(schema["properties"]) == {
        "selected_interpretation_ids", "needs_clarification", "missing_slots", "confidence"
    }
    assert schema["additionalProperties"] is False


def test_tool_schema_rejects_free_text_and_more_than_two_ids():
    with pytest.raises(ValidationError):
        MiniMaxAmbiguityPatch.model_validate({
            "selected_interpretation_ids": ["i0", "i1", "i2"],
            "needs_clarification": False,
            "missing_slots": [],
            "confidence": 0.8,
            "explanation": "not allowed",
        })
