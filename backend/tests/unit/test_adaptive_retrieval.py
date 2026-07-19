from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.query_understanding_service import QueryUnderstandingService


def test_exact_fault_and_model_use_keyword_first():
    router = AdaptiveRetrievalStrategy()
    analysis = QueryUnderstandingService().understand("SUN2000-100KTL-M2 告警 2064")
    result = router.route(analysis, requested_strategy="adaptive", reranker_enabled=True)
    assert result.actual_strategy == "keyword"
    assert result.fallback_strategy == "keyword"


def test_visual_descriptor_uses_vector_enhanced_hybrid():
    analysis = QueryUnderstandingService().understand("图片显示逆变器红色告警灯")
    result = AdaptiveRetrievalStrategy().route(analysis, requested_strategy="adaptive", reranker_enabled=False)
    assert result.actual_strategy == "hybrid"
    assert result.vector_weight > result.keyword_weight

