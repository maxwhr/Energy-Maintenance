from app.services.query_understanding_service import QueryUnderstandingService


def test_model_query_extracts_sun2000_variant():
    assert "SUN2000-33KTL" in QueryUnderstandingService().understand("SUN2000-33KTL 的维护说明").device_models
