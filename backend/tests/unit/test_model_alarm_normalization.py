from app.services.query_understanding_service import (
    QueryUnderstandingService, normalize_alarm_identifier, normalize_device_model, normalize_fault_name,
)


def test_model_alarm_normalization_for_huawei_families():
    assert normalize_device_model("SmartLogger 3000") == "SMARTLOGGER3000"
    assert normalize_device_model("LUNA2000–7-S1") == "LUNA2000-7-S1"
    assert normalize_alarm_identifier(" 20_32 ") == "20-32"
    assert normalize_fault_name("绝缘阻抗低（告警）") == "绝缘阻抗低告警"
    assert QueryUnderstandingService().understand("SUN2000 告警 2032").fault_codes == ["2032"]
