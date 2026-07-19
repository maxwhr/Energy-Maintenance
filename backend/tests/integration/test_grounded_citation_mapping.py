from tests.unit.test_maintenance_semantic_unit import source_objects
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService


def test_citation_mapping_uses_original_chunk_and_page_not_canonical_text() -> None:
    document, chunk = source_objects(("通信异常时检查线缆连接，操作前断电并接地，完成后验证恢复正常。") * 5)
    unit = MaintenanceSemanticUnitService.build_unit([chunk], document)
    assert unit is not None
    assert unit.source_chunk_ids == [str(chunk.id)]
    assert unit.source_locator["page_start"] == chunk.page_number
    assert "canonical_text" not in unit.source_locator

