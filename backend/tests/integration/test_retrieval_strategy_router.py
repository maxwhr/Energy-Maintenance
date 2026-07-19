from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.query_understanding_service import QueryUnderstandingService


def test_strategy_routes_safety_to_keyword_and_symptom_to_hybrid():
    router = AdaptiveRetrievalStrategy()
    safety = router.route(QueryUnderstandingService().understand("检修前断电验电 PPE 安全要求"), requested_strategy="adaptive", reranker_enabled=False)
    symptom = router.route(QueryUnderstandingService().understand("雨后逆变器间歇异常怎么排查"), requested_strategy="adaptive", reranker_enabled=False)
    assert safety.actual_strategy == "keyword"
    assert symptom.actual_strategy == "hybrid"

