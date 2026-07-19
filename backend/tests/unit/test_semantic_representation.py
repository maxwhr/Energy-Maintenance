from __future__ import annotations

from types import SimpleNamespace

from app.services.maintenance_semantic_representation_service import MaintenanceSemanticRepresentationService


def _source_objects() -> tuple[SimpleNamespace, SimpleNamespace]:
    chunk = SimpleNamespace(
        content="Source-only maintenance evidence: inspect the connector before restart.",
        metadata_json={}, page_number=7, section_title="Maintenance procedure", id="chunk-a",
    )
    document = SimpleNamespace(product_series="SUN2000", model="MODEL-X", metadata_json={"normalized_language": "zh-CN"})
    return chunk, document


def test_semantic_representation_is_reproducible_and_does_not_invent_causes() -> None:
    chunk, document = _source_objects()
    service = MaintenanceSemanticRepresentationService(None)
    first = service.build(chunk, document)
    second = service.build(chunk, document)
    assert first.representation_hash == second.representation_hash
    assert first.semantic_fields["possible_causes"] == []
    assert first.semantic_fields["source_excerpt"] == chunk.content
    assert first.source_locator["page_number"] == 7

