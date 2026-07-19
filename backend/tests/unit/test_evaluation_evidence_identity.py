import pytest
from pydantic import ValidationError

from app.schemas.retrieval_evaluation import EvaluationEvidenceIdentity


def test_relevant_identity_requires_locator_and_grades_are_explicit():
    with pytest.raises(ValidationError):
        EvaluationEvidenceIdentity(
            case_id="c1", evaluation_level="CHUNK", direct_evidence_ids=["chunk-1"],
            relevance_grades={"chunk-1": 3}, label_reason="direct answer", label_version="v1",
        )
    item = EvaluationEvidenceIdentity(
        case_id="c1", evaluation_level="CHUNK", direct_evidence_ids=["chunk-1"],
        source_locator={"page_start": 1}, relevance_grades={"chunk-1": 3},
        label_reason="direct answer", label_version="v1",
    )
    assert item.relevant_ids() == {"chunk-1"}
