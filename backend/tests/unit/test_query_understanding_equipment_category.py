from app.services.llm_query_understanding_service import LLMQueryUnderstandingService


def test_equipment_category_requires_model_evidence():
    assert LLMQueryUnderstandingService._equipment_categories([]) == []
    assert LLMQueryUnderstandingService._equipment_categories(["SUN2000-100KTL-M1"]) == ["pv_inverter"]
    assert LLMQueryUnderstandingService._equipment_categories(["LUNA2000"]) == ["energy_storage"]
    assert LLMQueryUnderstandingService._equipment_categories(["SmartLogger3000"]) == ["communication_management_device"]
