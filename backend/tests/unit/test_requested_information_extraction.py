from tests.r5_r5_test_helpers import understand


def test_configuration_is_information_type_not_primary_intent():
    result = understand("SmartLogger 的 RS485 地址和波特率怎么设置？")
    assert "CONFIGURATION" in result.requested_information
    assert result.primary_intent == "PROCEDURE"
    assert len(result.requested_information) <= 5
