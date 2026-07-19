from app.services.graded_relevance_metrics import direct_answer_hit, graded_mrr, ndcg


def test_graded_metrics_reward_direct_answer_earlier():
    good = [3, 2, 0]
    bad = [1, 0, 3]
    assert ndcg(good, 3) > ndcg(bad, 3)
    assert graded_mrr(good) > graded_mrr(bad)
    assert direct_answer_hit(good, 1) == 1
