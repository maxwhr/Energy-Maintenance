from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService


def test_typed_consistency_can_promote_a_relevant_unit() -> None:
    relevant = SemanticUnitRetrievalService.final_score(
        {"ACTION": 0.68, "PROCEDURE": 0.67}, ["ACTION", "PROCEDURE", "SAFETY"]
    )
    raw_nearest = SemanticUnitRetrievalService.final_score({"SAFETY": 0.70}, ["ACTION", "PROCEDURE", "SAFETY"])
    assert relevant > raw_nearest

