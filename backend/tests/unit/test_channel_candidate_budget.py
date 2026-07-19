from tests.r5_r5_test_helpers import plan


def test_channel_budgets_and_identity_limits_are_explicit():
    item = plan("SUN2000-50KTL 通信故障怎么处理？")
    assert item.channel_candidate_budgets == {
        "EXACT_KEYWORD": 30, "SCOPED_KEYWORD": 80, "RAW_VECTOR": 80, "SEMANTIC_UNIT": 100,
    }
    assert item.per_channel_identity_limit == 60
    assert item.fusion_candidate_limit == 150
    assert item.candidate_top_k == 50
