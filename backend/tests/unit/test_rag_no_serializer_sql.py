from app.services.query_aware_retrieval_service import QueryAwareRetrievalService
from app.services.rrf_fusion_service import QueryAwareCandidate


def test_flat_candidate_serialization_reads_no_relationships():
    item = QueryAwareCandidate(
        candidate_id="a", chunk_id="a", document_id="d", document_title="manual",
        content="source evidence", source_chunk_ids=["a"], scope_validation_passed=True,
    )
    value = QueryAwareRetrievalService._read(item).model_dump(mode="json")
    assert value["chunk_id"] == "a"
    assert value["quote"] == "source evidence"
