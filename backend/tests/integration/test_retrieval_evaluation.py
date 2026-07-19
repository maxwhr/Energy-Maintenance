from app.services.retrieval_evaluation_service import RetrievalEvaluationService


def test_retrieval_evaluation_metrics_known_ranking():
    metrics = RetrievalEvaluationService.compute_metrics(["a", "x", "b"], ["a", "b"])
    assert metrics["recall_at_1"] == .5
    assert metrics["recall_at_5"] == 1
    assert metrics["mrr"] == 1
    assert 0 < metrics["ndcg_at_10"] <= 1
