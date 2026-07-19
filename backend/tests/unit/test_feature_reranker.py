from app.services.feature_reranker import FeatureFusionReranker, RerankFeatures


def test_feature_reranker_is_bounded_and_rollback_guarded():
    service = FeatureFusionReranker()
    assert 0 <= service.score(RerankFeatures(keyword_score=1, vector_score=1, exact_fault_code=1)) <= 1
    assert service.should_rollback(.90, .88)
    assert not service.should_rollback(.90, .895)
    assert service.snapshot()["test_split_tuning_allowed"] is False
