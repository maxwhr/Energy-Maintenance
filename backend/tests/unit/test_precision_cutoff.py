from types import SimpleNamespace
from uuid import uuid4

from app.services.retrieval_precision_policy import RetrievalPrecisionPolicy


def _candidate(score, document_id, *, exact=False):
    return SimpleNamespace(
        score=score,
        document=SimpleNamespace(id=document_id),
        exact_model_boost=0.12 if exact else 0.0,
        exact_fault_code_boost=0.0,
    )


def test_precision_cutoff_prioritizes_top_three_and_document_diversity():
    one, two, three = uuid4(), uuid4(), uuid4()
    candidates = [
        _candidate(0.90, one), _candidate(0.80, one), _candidate(0.70, two),
        _candidate(0.30, one), _candidate(0.60, three), _candidate(0.10, three),
    ]
    output, diagnostics = RetrievalPrecisionPolicy.apply(candidates, requested_top_k=8, minimum_score=0.2)
    assert len(output) == 4
    assert output[-1].document.id == three
    assert diagnostics["maximum_displayed"] == 5
    assert diagnostics["collapsed"] == 2
