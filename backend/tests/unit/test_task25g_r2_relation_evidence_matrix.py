from app.services.kg_relation_evidence_type_matrix import KGRelationEvidenceTypeMatrix


def test_relation_matrix_is_versioned_and_rejects_full_section_as_direct_support():
    rule = KGRelationEvidenceTypeMatrix.relation_rule("HAS_SYMPTOM")
    assert rule is not None
    assert "告警" in rule.relation_cues
    assert KGRelationEvidenceTypeMatrix.relation_type_compatible("HAS_SYMPTOM", "ALARM")
    assert not KGRelationEvidenceTypeMatrix.relation_type_compatible("HAS_SYMPTOM", "FULL_SECTION")
    assert KGRelationEvidenceTypeMatrix.VERSION == "task25g_r2_relation_evidence_matrix_v1"

