from scripts.task25b_r3_dev_common import quality_decision


def test_quality_gate_rejects_missing_chunks():
    class Doc:
        metadata_json = {"normalized_language": "zh-CN", "source_provenance": "VENDOR_OFFICIAL",
                         "parser_success": True, "equipment_categories": ["pv_inverter"],
                         "chinese_character_ratio": 1.0}
        source = "https://support.huawei.com/enterprise/zh/doc/example"
        document_type = "USER_MANUAL"
        product_series = "SUN2000"
        parse_status = "parsed"
    passed, reasons, _ = quality_decision(Doc(), [])
    assert passed is False
    assert "no_chunks" in reasons
