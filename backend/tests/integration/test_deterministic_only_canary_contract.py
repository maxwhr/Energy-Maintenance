from app.core.config import Settings
from app.services.query_signal_extraction_service import QuerySignalExtractionService
from app.services.question_completeness_service import QuestionCompletenessService
from app.services.query_understanding_orchestrator_service import QueryUnderstandingOrchestratorService


def test_deterministic_only_contract_never_requires_cloud_precondition():
    settings = Settings(
        _env_file=None,
        MINIMAX_ENABLED=False,
        TASK25B_ALLOW_REAL_API=False,
        RAG_MINIMAX_AMBIGUITY_RESOLVER_ENABLED=False,
    )
    queries = [
        "SUN2000-50KTL 告警代码 2001 是什么意思？",
        "通信为什么总是中断？",
        "高压场景检查要注意什么？",
        "设备没反应",
    ] * 15
    service = QueryUnderstandingOrchestratorService(settings=settings)
    results = []
    for query in queries:
        signals = QuerySignalExtractionService().extract(query)
        results.append(service.understand(
            signals=signals,
            assessment=QuestionCompletenessService().assess(signals),
            enable_llm=False,
            allow_real_api=False,
        ).understanding)
    assert len(results) == 60
    assert all(item.actual_provider == "deterministic" for item in results)
    assert all(item.structured_model_diagnostics["external_call_count"] == 0 for item in results)
