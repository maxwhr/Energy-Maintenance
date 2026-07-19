from app.services.query_understanding_service import QueryUnderstandingService


def test_alarm_query_extracts_explicit_code():
    assert "1234" in QueryUnderstandingService().understand("告警 1234 的处理方法").fault_codes
