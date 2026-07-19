from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.query_understanding_service import QueryUnderstandingService


def test_visual_and_colloquial_symptoms_get_vector_enhanced_candidates():
    router = AdaptiveRetrievalStrategy()
    visual = router.route(QueryUnderstandingService().understand("照片里告警屏发红但看不清型号"), requested_strategy="adaptive", reranker_enabled=False)
    symptom = router.route(QueryUnderstandingService().understand("雨后机器偶尔掉线又自己恢复"), requested_strategy="adaptive", reranker_enabled=False)
    assert visual.actual_strategy == "hybrid"
    assert visual.vector_weight > visual.keyword_weight
    assert symptom.actual_strategy in {"hybrid", "keyword"}
