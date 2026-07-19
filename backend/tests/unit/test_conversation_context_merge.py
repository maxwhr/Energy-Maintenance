from app.services.conversation_retrieval_context_service import ConversationRetrievalContextService
from app.services.query_signal_extraction_service import QuerySignalExtractionService


def test_only_explicit_clarification_facts_are_eligible_for_merge() -> None:
    signals = QuerySignalExtractionService().extract("型号是 SUN2000-100KTL-M1，现象是通信中断")
    facts = ConversationRetrievalContextService._fact_dict(signals)
    assert facts["device_models"] == ["SUN2000-100KTL-M1"]
    assert "通信中断" in facts["symptoms"]
    assert "hypotheses" not in facts
    assert ConversationRetrievalContextService._resolved("device_model", facts)
    assert ConversationRetrievalContextService._resolved("specific_symptom_or_alarm_code", facts)
