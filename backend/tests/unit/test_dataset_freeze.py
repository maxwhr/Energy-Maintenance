from types import SimpleNamespace

from app.services.retrieval_pilot_service import RetrievalPilotService


def _case(category="safety_procedure", *, vector=False, hard=False, second=True):
    return SimpleNamespace(
        review_status="expert_verified",
        category=category,
        metadata_json={"vector_heavy": vector, "hard_negative": hard, "second_reviews": [{}] if second else []},
    )


def test_dataset_freeze_requires_real_expert_volume_and_coverage():
    ready, failures = RetrievalPilotService._readiness([])
    assert ready is False
    assert any("expert_verified" in item for item in failures)

    cases = [_case() for _ in range(55)] + [_case("multimodal_descriptor", vector=True) for _ in range(20)]
    cases += [_case("no_answer", hard=True) for _ in range(15)] + [_case("symptom_query") for _ in range(10)]
    ready, failures = RetrievalPilotService._readiness(cases)
    assert ready is True, failures
