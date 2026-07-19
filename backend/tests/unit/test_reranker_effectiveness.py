from app.services.feature_reranker import FeatureFusionReranker, RerankFeatures


def test_exact_features_change_rerank_score():
    reranker = FeatureFusionReranker()
    generic = reranker.score(RerankFeatures(keyword_score=.7, vector_score=.7))
    exact = reranker.score(RerankFeatures(keyword_score=.7, vector_score=.4, exact_device_model=1, exact_fault_code=1))
    assert exact > generic
    assert reranker.snapshot()["version"] == "feature_fusion_v2"

