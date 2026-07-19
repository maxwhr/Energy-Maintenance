from app.services.grounded_benchmark_validation import grounded_query, topic_hint


def test_grounded_query_uses_partial_source_hint_without_ids() -> None:
    unit = {
        "source_section": "6.3.25 设置 Echonet", "device_models": ["SUN2000-50KTL"], "alarm_codes": [],
        "component_terms": ["通信"], "symptom_terms": ["异常"], "cause_terms": [], "action_terms": ["设置"],
        "safety_terms": [], "prerequisite_terms": [], "verification_terms": [], "semantic_unit_type": "COMMUNICATION",
    }
    query, concepts = grounded_query(unit)
    assert topic_hint(unit) == "Echonet"
    assert "Echonet" in query and "6.3.25 设置 Echonet" not in query
    assert "SUN2000-50KTL" not in query and concepts[0] == "Echonet"
