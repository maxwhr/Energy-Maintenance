from app.services.kg_current_chinese_evidence_matcher import KGCurrentChineseEvidenceMatcher


def test_edge_requires_explicit_relation_in_same_or_grounded_multi_span():
    same, _ = KGCurrentChineseEvidenceMatcher._same_span_support(
        ["绝缘阻抗低。", "告警。"], ["绝缘阻抗低"], ["告警"], ("出现", "触发")
    )
    multi, _ = KGCurrentChineseEvidenceMatcher._multi_span_support(
        ["绝缘阻抗低。", "告警。"], ["绝缘阻抗低"], ["告警"], ("出现", "触发")
    )
    assert not same
    assert not multi
    same, _ = KGCurrentChineseEvidenceMatcher._same_span_support(
        ["绝缘阻抗低会触发告警。"], ["绝缘阻抗低"], ["告警"], ("触发",)
    )
    assert same

