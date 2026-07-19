from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService


def test_typed_consistency_and_primary_intent_raise_unit_score() -> None:
    single = SemanticUnitRetrievalService.final_score({"ACTION": 0.70}, ["ACTION", "PROCEDURE", "SAFETY"])
    multiple = SemanticUnitRetrievalService.final_score(
        {"ACTION": 0.70, "PROCEDURE": 0.68}, ["ACTION", "PROCEDURE", "SAFETY"]
    )
    assert single == 0.725
    assert multiple > single

