import os
import pytest

from app.core.database import SessionLocal
from app.services.llm_query_understanding_service import LLMQueryUnderstandingService
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService


@pytest.mark.skipif(os.getenv("R5_R1_RUN_REAL_TESTS") != "true", reason="explicit real API integration only")
def test_real_structured_query_understanding():
    signals = QuerySignalExtractionService().extract("通信总是掉线，先查什么")
    with SessionLocal() as db:
        result = LLMQueryUnderstandingService(db).understand(signals=signals, assessment=QuestionCompletenessService().assess(signals), enable_llm=True)
    assert result.structured_model_diagnostics.get("success") is True
