from app.services.graded_relevance_metrics import direct_answer_hit, ndcg, requested_information_coverage_at_k


def test_graded_pipeline_reports_direct_hits_and_aggregate_request_coverage():
    grades = [3, 2, 1]
    support = [{"CAUSE"}, {"ACTION"}, {"SAFETY"}]
    assert ndcg(grades, 3) == 1.0
    assert direct_answer_hit(grades, 1) == 1.0
    assert requested_information_coverage_at_k(support, {"CAUSE", "ACTION"}, 3) == 1.0
