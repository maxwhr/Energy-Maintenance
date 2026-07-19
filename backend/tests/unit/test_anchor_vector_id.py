from __future__ import annotations

from app.services.maintenance_semantic_representation_service import MaintenanceSemanticRepresentationService


def test_anchor_vector_id_is_stable_and_type_scoped() -> None:
    first = MaintenanceSemanticRepresentationService.anchor_vector_id("chunk-1", "FULL_SEMANTIC")
    assert first == MaintenanceSemanticRepresentationService.anchor_vector_id("chunk-1", "FULL_SEMANTIC")
    assert first != MaintenanceSemanticRepresentationService.anchor_vector_id("chunk-1", "ACTION")
    assert first != MaintenanceSemanticRepresentationService.anchor_vector_id("chunk-2", "FULL_SEMANTIC")
    assert first.startswith("sa_")

