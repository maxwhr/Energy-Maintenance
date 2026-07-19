from app.services.semantic_unit_retrieval_service import SemanticUnitRetrievalService


def test_expected_unit_survives_multi_anchor_candidate_merge() -> None:
    merged = SemanticUnitRetrievalService.merge_unit_records([
        ("expected", "COMMUNICATION", 0.55, 0.9),
        *[(f"negative-{index}", "COMMUNICATION", 0.54 - index / 1000, 1.0) for index in range(49)],
    ])
    ranked = sorted(merged, key=lambda unit_id: -max(merged[unit_id]["scores"].values()))
    assert "expected" in ranked[:50]

