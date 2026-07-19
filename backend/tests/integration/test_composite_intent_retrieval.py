from tests.r5_r5_test_helpers import plan, understand


def test_composite_information_reaches_request_query_and_anchor_union():
    understanding = understand("通信为什么掉线，怎么处理并确认恢复？")
    item = plan("通信为什么掉线，怎么处理并确认恢复？")
    assert understanding.primary_intent == "TROUBLESHOOTING"
    assert {"CAUSE", "ACTION", "VERIFICATION"} <= set(understanding.requested_information)
    assert "REQUEST_QUERY" in {value.variant_type for value in item.query_variants}
    assert {"CAUSE", "ACTION", "VERIFICATION"} <= set(item.anchor_types)
