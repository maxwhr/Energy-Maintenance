from app.services.query_understanding_service import QueryUnderstandingService


def test_vector_heavy_query_has_no_model_or_alarm_anchor():
    analysis = QueryUnderstandingService().understand("后台持续收不到设备状态时，应从数据链路的哪些环节检查？")
    assert not analysis.device_models
    assert not analysis.fault_codes
