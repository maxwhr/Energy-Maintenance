from app.services.query_understanding_service import QueryUnderstandingService


def test_query_understanding_preserves_model_fault_and_normalizes_width():
    result = QueryUnderstandingService().understand("ＳＵＮ２０００-100KTL 告警 2064 雨后绝缘低怎么排查")
    assert "SUN2000-100KTL" in result.device_models
    assert "2064" in result.fault_codes
    assert "2000" not in result.fault_codes
    assert result.query_intent == "alarm_code_query"
    assert result.kg_alias_terms
