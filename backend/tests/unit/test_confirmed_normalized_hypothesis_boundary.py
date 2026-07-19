from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


def test_confirmed_facts_and_normalized_semantics_are_separate():
    signals = QuerySignalExtractionService().extract("SUN2000-100KTL-M1 老是掉线")
    result = LLMQueryUnderstandingService._deterministic(signals, QuestionCompletenessService().assess(signals))
    assert result.confirmed_facts["device_models"] == ["SUN2000-100KTL-M1"]
    assert result.normalized_semantics is not result.confirmed_facts
    assert result.retrieval_hypotheses == []
