from tests.unit.test_maintenance_semantic_unit import source_objects
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService


def test_procedure_unit_preserves_prerequisite_action_verification_context() -> None:
    content = ("维护操作步骤：操作之前确保设备断电并准备绝缘工具。检查并更换风扇组件，"
               "完成后验证告警消失且设备正常运行；如仍异常则停止操作。") * 3
    document, chunk = source_objects(content, "风扇组件维护步骤")
    unit = MaintenanceSemanticUnitService.build_unit([chunk], document)
    assert unit is not None and unit.semantic_unit_type in {"PROCEDURE", "SAFETY"}
    assert unit.action_terms and unit.safety_terms
    assert "PROCEDURE" in unit.anchor_types or unit.semantic_unit_type == "SAFETY"
