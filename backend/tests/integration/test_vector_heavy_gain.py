from app.services.adaptive_retrieval_strategy import AdaptiveRetrievalStrategy
from app.services.query_understanding_service import QueryUnderstanding


def test_unanchored_semantic_symptom_routes_to_hybrid():
    decision = AdaptiveRetrievalStrategy().route(QueryUnderstanding(normalized_query="语义症状", query_intent="fault_diagnosis", symptom_terms=["症状"]), requested_strategy="adaptive", reranker_enabled=False)
    assert decision.actual_strategy == "hybrid"
    assert decision.vector_weight > decision.keyword_weight
