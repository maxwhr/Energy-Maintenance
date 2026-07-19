from __future__ import annotations

from types import SimpleNamespace

from app.services.maintenance_semantic_representation_service import MaintenanceSemanticRepresentationService


def test_full_anchor_comes_from_source_representation() -> None:
    service = MaintenanceSemanticRepresentationService(None)
    chunk = SimpleNamespace(content="A documented maintenance instruction.", metadata_json={}, page_number=3, section_title="Checks", id="chunk-1")
    document = SimpleNamespace(product_series="SUN2000", model="MODEL-Y", metadata_json={})
    representation = service.build(chunk, document)
    anchor = service._anchor_text("FULL_SEMANTIC", representation)
    assert anchor == representation.canonical_retrieval_text
    assert "documented maintenance instruction" in anchor

