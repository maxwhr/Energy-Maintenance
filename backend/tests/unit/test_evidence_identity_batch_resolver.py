from app.services.evidence_identity_batch_resolver import EvidenceIdentityBatchResolver
from app.services.rrf_fusion_service import QueryAwareCandidate


def candidate(candidate_id: str):
    return QueryAwareCandidate(
        candidate_id=candidate_id,
        chunk_id="chunk-a",
        document_id="doc-a",
        document_title="manual",
        content="evidence",
        source_chunk_ids=["chunk-a"],
    )


def test_identity_is_resolved_once_and_reused_without_dropping_candidates():
    first = candidate("same")
    second = candidate("same")
    result = EvidenceIdentityBatchResolver().resolve({"a": [first], "b": [second]})
    assert first.evidence_equivalence_key == second.evidence_equivalence_key
    assert result["identity_reuse_count"] == 1
    assert result["candidates_dropped"] == 0
