from app.services.maintenance_semantic_unit_v2_service import MaintenanceSemanticUnitV2Service
from app.services.semantic_section_assembler import SemanticSectionAssembler
from tests.unit.test_semantic_unit_v2 import source_rows


def test_unrepresented_maintenance_section_is_recoverable() -> None:
    rows = source_rows("出现无法启动时，可能原因是直流开关未闭合。检查直流开关并确认设备恢复正常。" * 4)
    section = SemanticSectionAssembler.assemble(rows)[0]
    audit = MaintenanceSemanticUnitV2Service.classify_unrepresented(section)
    assert audit["recoverable"] is True
    assert audit["classification"] in {
        "SYMPTOM_STRUCTURE_MISSED", "CAUSE_STRUCTURE_MISSED", "ACTION_STRUCTURE_MISSED", "CROSS_CHUNK_FACT"
    }
    assert audit["source_locator_valid"] is True


def test_noise_and_missing_locator_do_not_enter_recovery() -> None:
    rows = source_rows("本手册目录和版权声明。" * 12, page=None)
    rows[0][0].section_title = "目录"
    section = SemanticSectionAssembler.assemble(rows)[0]
    audit = MaintenanceSemanticUnitV2Service.classify_unrepresented(section)
    assert audit["recoverable"] is False
    assert audit["classification"] == "TABLE_OF_CONTENTS"
