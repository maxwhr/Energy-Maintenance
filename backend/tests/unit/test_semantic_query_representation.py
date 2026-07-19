from __future__ import annotations

from app.services.semantic_query_representation_service import SemanticQueryRepresentationService


def test_query_representation_retains_query_without_label_injection() -> None:
    representation = SemanticQueryRepresentationService().build("communication interruption requires inspection")
    assert representation.normalized_query
    assert representation.normalized_query in representation.semantic_query_text
    assert "expected_chunk" not in representation.semantic_query_text
    assert "benchmark" not in representation.semantic_query_text.lower()

