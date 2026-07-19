from app.services.kg_current_chinese_evidence_matcher import KGCurrentChineseEvidenceMatcher


def test_chinese_same_span_matching_does_not_depend_on_spaces():
    supported, details = KGCurrentChineseEvidenceMatcher._same_span_support(
        ["逆变器出现绝缘阻抗低告警时，应先停机排查直流侧。"],
        ["绝缘阻抗低"],
        ["告警"],
        ("出现", "告警"),
    )
    assert supported
    assert details[0]["subject_terms"] == ["绝缘阻抗低"]
    assert not KGCurrentChineseEvidenceMatcher._has_relevant_conflict(
        ["本章节不支持其他型号。绝缘阻抗低会触发告警。"], ["绝缘阻抗低"], ["告警"]
    )

