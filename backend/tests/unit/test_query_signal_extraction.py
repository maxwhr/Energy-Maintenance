from app.services.query_signal_extraction_service import QuerySignalExtractionService


def test_extracts_model_alarm_condition_symptom_and_intent_without_cross_contamination() -> None:
    result = QuerySignalExtractionService().extract(
        "SUN2000-100KTL-M1 晚上并网后告警代码 2002，为什么会通信中断？"
    )
    assert result.device_models == ["SUN2000-100KTL-M1"]
    assert result.model_original == "SUN2000-100KTL-M1"
    assert result.model == "SUN2000-100KTL-M1"
    assert result.model_confidence == 0.98
    assert result.manufacturer == "huawei"
    assert result.product_family == "SUN2000"
    assert result.alarm_codes == ["2002"]
    assert "SUN2000" not in result.alarm_codes
    assert "CAUSE" in result.requested_information
    assert "通信中断" in result.symptoms
    assert "晚上" in result.time_conditions


def test_width_normalization_and_colloquial_action_intent() -> None:
    result = QuerySignalExtractionService().extract("ＳＵＮ２０００-50KTL 过温了咋整")
    assert result.device_models == ["SUN2000-50KTL"]
    assert "TROUBLESHOOTING" not in result.action_intent
    assert "ACTION" in result.action_intent


def test_extracts_explicit_chinese_alarm_name_without_inventing_code() -> None:
    result = QuerySignalExtractionService().extract("出现“系统接地异常”告警时怎么处理？")
    assert result.alarm_names == ["系统接地异常"]
    assert result.alarm_codes == []


def test_normalizes_huawei_aliases_and_sun2000_model_variants() -> None:
    service = QuerySignalExtractionService()
    cases = {
        "华为 SUN2000 绝缘阻抗低": "SUN2000",
        "HUAWEI SUN 2000 通信不上": "SUN2000",
        "华为光伏 SUN2000-100KTL 通讯不上": "SUN2000-100KTL",
        "SUN2000 100KTL M1 通迅不上": "SUN2000-100KTL-M1",
        "sun2000-100ktl-m1 温度太高": "SUN2000-100KTL-M1",
    }
    for query, expected_model in cases.items():
        result = service.extract(query)
        assert result.manufacturer == "huawei"
        assert result.product_family == "SUN2000"
        assert result.model == expected_model
        assert result.model_original


def test_recognizes_fusionsolar_as_huawei_related_product_family() -> None:
    result = QuerySignalExtractionService().extract("FusionSolar 离线后如何排查")
    assert result.manufacturer == "huawei"
    assert result.product_family == "FusionSolar"
    assert result.fault_type == "communication_interruption"


def test_numeric_alarm_codes_require_known_code_or_explicit_alarm_context() -> None:
    service = QuerySignalExtractionService()
    positives = (
        "华为 2061 告警",
        "2061 告警",
        "故障码 2061",
        "告警代码2061",
        "SUN2000 2061",
        "2061 怎么处理",
        "SUN2000 告警代码 2002",
    )
    for query in positives:
        assert service.extract(query).alarm_code in {"2061", "2002"}

    negatives = (
        "2026 年设备发生告警",
        "1100V 输入电压",
        "第 2061 页",
        "100kW 逆变器",
        "2026-07-16",
        "普通编号 123456 与逆变器无关",
    )
    for query in negatives:
        assert service.extract(query).alarm_code is None


def test_normalizes_required_chinese_fault_expressions() -> None:
    service = QuerySignalExtractionService()
    cases = {
        "华为逆变器通迅不上": "communication_interruption",
        "SUN2000 低绝缘": "low_insulation_resistance",
        "SUN2000 温度太高": "over_temperature",
        "MPPT 效率低": "mppt_abnormal",
        "并网失败": "grid_connection_fault",
    }
    for query, expected_fault_type in cases.items():
        result = service.extract(query)
        assert result.fault_type == expected_fault_type


def test_detects_formal_scope_violations_without_blocking_huawei_queries() -> None:
    service = QuerySignalExtractionService()
    assert service.unsupported_scope_reason("华为 SUN2000 绝缘阻抗低") is None
    assert service.unsupported_scope_reason("FusionSolar 夜间离线") is None
    assert service.unsupported_scope_reason("阳光电源 SG110CX 告警") == "unsupported_manufacturer"
    assert service.unsupported_scope_reason("LUNA2000 电池故障") == "unsupported_luna2000_product"
    assert service.unsupported_scope_reason("SmartLogger 通信不上") == "unsupported_smartlogger_product"
    assert service.unsupported_scope_reason("逆变器告警", manufacturer="sungrow") == "unsupported_manufacturer"
