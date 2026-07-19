from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService


def test_multiple_anchor_hits_merge_once_by_semantic_unit() -> None:
    merged = SemanticUnitRetrievalService.merge_unit_records([
        ("su-1", "SYMPTOM", 0.61, 0.78), ("su-1", "ACTION", 0.72, 0.56),
        ("su-1", "ACTION", 0.69, 0.60), ("su-2", "SAFETY", 0.66, 0.68),
    ])
    assert set(merged) == {"su-1", "su-2"}
    assert merged["su-1"]["scores"] == {"SYMPTOM": 0.61, "ACTION": 0.72}
    assert merged["su-1"]["hits"] == 3

