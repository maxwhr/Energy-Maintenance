from tests.r5_r5_test_helpers import plan


def test_planner_v3_keeps_original_and_uses_only_five_named_variants():
    item = plan("SUN2000 夜间通信掉线是什么原因，怎么处理并验证恢复？")
    assert item.query_variants[0].variant_type == "ORIGINAL"
    assert len(item.query_variants) <= 5
    assert {value.variant_type for value in item.query_variants} <= {
        "ORIGINAL", "CANONICAL", "SYMPTOM_QUERY", "REQUEST_QUERY", "CONDITION_QUERY"
    }
    assert all(value.purpose for value in item.query_variants)
