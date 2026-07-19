from tests.unit.test_maintenance_semantic_unit import source_objects
from app.models import KnowledgeChunk
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService


def test_one_unit_can_map_multiple_adjacent_direct_source_chunks() -> None:
    document, first = source_objects(("检修通信模块前确认断电和接地，检查线缆与端子连接。") * 5, "通信模块检修")
    second = KnowledgeChunk(
        id=__import__("uuid").uuid4(), document_id=document.id, manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="manual", chunk_index=1,
        content=("完成连接后重新启动设备，验证通信恢复正常并记录检查结果。") * 5,
        char_count=150, section_title="通信模块检修", page_number=13, status="active",
        metadata_json={"heading_path": ["通信模块检修"], "current_chunk_version": True},
    )
    unit = MaintenanceSemanticUnitService.build_unit([first, second], document)
    assert unit is not None
    assert unit.source_chunk_ids == [str(first.id), str(second.id)]
    assert unit.source_page_start == 12 and unit.source_page_end == 13

