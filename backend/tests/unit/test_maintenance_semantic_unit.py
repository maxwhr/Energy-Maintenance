from uuid import uuid4

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService


def source_objects(content: str, section: str = "通信异常处理"):
    document_id = uuid4()
    document = KnowledgeDocument(
        id=document_id, title="工程手册", manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="manual", review_status="approved", status="active",
        metadata_json={"normalized_language": "zh-CN", "approved_for_pilot": True, "equipment_categories": ["pv_inverter"]},
    )
    chunk = KnowledgeChunk(
        id=uuid4(), document_id=document_id, manufacturer="huawei", product_series="SUN2000",
        device_type="pv_inverter", document_type="manual", chunk_index=0, content=content,
        char_count=len(content), section_title=section, page_number=12, status="active",
        metadata_json={"heading_path": [section], "current_chunk_version": True},
    )
    return document, chunk


def test_semantic_unit_is_stable_source_grounded_and_traceable() -> None:
    content = ("通信模块出现离线异常时，先检查RS485线缆连接和地址设置，确认接地与安全防护，"
               "然后重新连接并验证设备恢复正常运行。") * 3
    document, chunk = source_objects(content)
    first = MaintenanceSemanticUnitService.build_unit([chunk], document)
    second = MaintenanceSemanticUnitService.build_unit([chunk], document)
    assert first is not None and second is not None
    assert first.semantic_unit_id == second.semantic_unit_id
    assert first.source_chunk_ids == [str(chunk.id)]
    assert first.source_locator["page_start"] == 12
    assert first.quality_status == "ENGINEERING_VERIFIED_SOURCE_GROUNDED"
    assert first.representation_version == "task25b_r3_dev_r4_semantic_unit_v1"

