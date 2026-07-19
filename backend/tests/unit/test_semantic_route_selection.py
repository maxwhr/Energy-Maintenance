from __future__ import annotations

from app.services.semantic_query_representation_service import SemanticQueryRepresentationService


def test_vector_heavy_route_never_silently_falls_back_to_keyword() -> None:
    route, fallback, reason = SemanticQueryRepresentationService.semantic_route_for_vector_heavy(semantic_partition_available=True)
    assert (route, fallback, reason) == ("semantic_vector", False, None)
    route, fallback, reason = SemanticQueryRepresentationService.semantic_route_for_vector_heavy(semantic_partition_available=False)
    assert route == "semantic_vector"
    assert fallback is False
    assert reason == "semantic_partition_unavailable"

