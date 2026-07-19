from app.services.retrieval_evaluation_service import RetrievalEvaluationService


def test_union_candidate_recall_at_50_is_layered():
    result = RetrievalEvaluationService.compute_staged_metrics(
        keyword_candidates=["a"], vector_candidates=["b"], final_ranked=["b", "a"], expected=["b"],
        no_answer=False, predicted_abstention=False,
    )
    assert result["candidate"]["union_candidate_recall_at_50"] == 1
    assert result["ranking"]["first_relevant_rank"] == 1

