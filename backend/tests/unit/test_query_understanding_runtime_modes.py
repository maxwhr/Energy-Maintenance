from app.core.config import Settings
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService


def _mode(query: str):
    signals = QuerySignalExtractionService().extract(query)
    return QueryUnderstandingOrchestratorService(settings=Settings(_env_file=None)).understand(
        signals=signals,
        assessment=QuestionCompletenessService().assess(signals),
        enable_llm=False,
        allow_real_api=False,
    ).understanding.query_understanding_mode


def test_deterministic_runtime_modes():
    assert _mode("SUN2000-50KTL 告警代码 2001 是什么意思？") == "FAST_PATH"
    assert _mode("通信为什么总是中断？") == "DETERMINISTIC"
    assert _mode("设备没反应") == "DETERMINISTIC_WITH_CLARIFICATION"
