from __future__ import annotations

from app.services.semantic_anchor_retrieval_service import SemanticAnchorRetrievalService


def test_anchor_hits_merge_to_one_source_chunk_with_controlled_score_inputs() -> None:
    merged = SemanticAnchorRetrievalService.merge_anchor_records([
        ("chunk-1", "FULL_SEMANTIC", 0.61, 0.61),
        ("chunk-1", "ACTION", 0.72, 0.72),
        ("chunk-2", "SAFETY", 0.70, 0.70),
    ])
    assert set(merged) == {"chunk-1", "chunk-2"}
    assert merged["chunk-1"]["score"] == 0.72
    assert merged["chunk-1"]["raw_score"] == 0.61
    assert merged["chunk-1"]["scores"] == {"FULL_SEMANTIC": 0.61, "ACTION": 0.72}

