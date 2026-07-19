from app.services.kg_evidence_equivalence_service import KGEvidenceEquivalenceService


def test_deterministic_equivalence_requires_all_fact_terms():
    matched, missing = KGEvidenceEquivalenceService.compare_text(
        "检查 SUN2000 逆变器的绝缘阻抗并记录结果。",
        ["SUN2000", "绝缘阻抗"],
    )
    assert matched == ("SUN2000", "绝缘阻抗")
    assert missing == ()


def test_partial_support_is_not_exact_support():
    matched, missing = KGEvidenceEquivalenceService.compare_text("检查 SUN2000 告警。", ["SUN2000", "绝缘阻抗"])
    assert matched == ("SUN2000",)
    assert missing == ("绝缘阻抗",)

