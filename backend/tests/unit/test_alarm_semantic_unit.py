from tests.unit.test_maintenance_semantic_unit import source_objects
from app.services.maintenance_semantic_unit_service import MaintenanceSemanticUnitService


def test_alarm_unit_keeps_code_cause_action_and_safety_together() -> None:
    content = ("告警代码3051：通信中断。可能原因是RS485线缆松动。检查并紧固连接端子，"
               "操作前断电并做好接地防护，完成后验证通信恢复正常。") * 3
    document, chunk = source_objects(content, "告警3051处理")
    chunk.metadata_json["fault_codes"] = ["3051"]
    unit = MaintenanceSemanticUnitService.build_unit([chunk], document)
    assert unit is not None and unit.semantic_unit_type == "ALARM"
    assert "3051" in unit.alarm_codes
    assert {"ALARM", "SYMPTOM", "CAUSE", "ACTION", "SAFETY"}.issubset(unit.anchor_types)

