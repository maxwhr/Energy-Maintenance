from app.schemas.retrieval_evaluation import RetrievalEvaluationRequest


def test_evaluation_request_accepts_frozen_test_v3_split():
    assert RetrievalEvaluationRequest(dataset_split="test_v3").dataset_split == "test_v3"
