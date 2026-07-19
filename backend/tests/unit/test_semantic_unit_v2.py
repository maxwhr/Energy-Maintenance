from uuid import uuid4

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.maintenance_semantic_unit_v2_service import MaintenanceSemanticUnitV2Service
from app.services.semantic_section_assembler import SemanticSectionAssembler
from app.services.source_grounding_validator import SourceGroundingValidator


def source_rows(content: str, *, page: int | None = 12):
    document_id = uuid4()
    document = KnowledgeDocument(
        id=document_id,
        title="SUN2000 中文维护手册",
        manufacturer="huawei",
        product_series="SUN2000",
        model="SUN2000-100KTL-M1",
        device_type="pv_inverter",
        document_type="manual",
        review_status="approved",
        status="active",
        metadata_json={
            "normalized_language": "zh-CN",
            "approved_for_pilot": True,
            "engineering_approved_for_pilot": True,
            "equipment_categories": ["pv_inverter"],
        },
    )
    chunk = KnowledgeChunk(
        id=uuid4(),
        document_id=document_id,
        manufacturer="huawei",
        product_series="SUN2000",
        device_type="pv_inverter",
        document_type="manual",
        chunk_index=0,
        content=content,
        char_count=len(content),
        section_title="通信异常处理",
        page_number=page,
        status="active",
        metadata_json={"heading_path": ["维护", "通信异常处理"], "current_chunk_version": True},
    )
    return [(chunk, document)]


def test_semantic_unit_v2_is_stable_typed_and_source_grounded() -> None:
    content = (
        "通信中断时，可能原因是RS485线缆连接松动。操作前必须断电并等待放电完成。"
        "检查通信模块与端子连接，然后重新连接线缆。操作完成后确认通信恢复正常。"
    ) * 3
    section = SemanticSectionAssembler.assemble(source_rows(content))[0]
    first = MaintenanceSemanticUnitV2Service.build_units(section, recoverable=True)
    second = MaintenanceSemanticUnitV2Service.build_units(section, recoverable=True)
    assert first
    assert [item.semantic_unit_id for item in first] == [item.semantic_unit_id for item in second]
    assert {item.unit_type for item in first} & {"COMMUNICATION", "CAUSE", "ACTION", "PROCEDURE"}
    assert all(item.representation_version == "task25b_r3_dev_r5_semantic_unit_v2" for item in first)
    assert all(item.engineering_verified and not item.expert_verified for item in first)
    assert all(SourceGroundingValidator().validate(item.public_dict(), section.chunks, section.document).passed for item in first)


def test_source_grounding_rejects_unsupported_fact_and_missing_locator() -> None:
    section = SemanticSectionAssembler.assemble(source_rows("检查线缆连接，确认通信恢复正常。" * 8, page=None))[0]
    unit = MaintenanceSemanticUnitV2Service.build_units(section, recoverable=True)[0].public_dict()
    unit["actions"].append("更换并不存在的功率模块")
    result = SourceGroundingValidator().validate(unit, section.chunks, section.document)
    assert not result.passed
    assert "source_locator_invalid" in result.failures
    assert any(value.startswith("actions:") for value in result.unsupported_fields)


def test_v2_vector_id_is_partition_representation_stable() -> None:
    value = MaintenanceSemanticUnitV2Service.vector_id("su2-a", "ACTION")
    assert value == MaintenanceSemanticUnitV2Service.vector_id("su2-a", "ACTION")
    assert value != MaintenanceSemanticUnitV2Service.vector_id("su2-a", "SAFETY")
    assert value.startswith("suva2_")
