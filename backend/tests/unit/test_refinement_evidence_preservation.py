from app.services.result_set_refinement_service import ResultSetRefinementService
from app.services.rrf_fusion_service import QueryAwareCandidate


def _c(value, source):
    return QueryAwareCandidate(candidate_id=value, chunk_id=value, document_id="d", document_title="m", content="e", section_title="s", source_chunk_ids=[source], source_locator={"section": "s"}, scope_validation_passed=True)


def test_same_section_merge_preserves_source_ids():
    result = ResultSetRefinementService().refine_query_aware([_c("a", "s1"), _c("b", "s2")], requested_top_k=5)
    assert len(result.surfaced) == 1
    assert result.surfaced[0].source_chunk_ids == ["s1", "s2"]
    assert result.diagnostics["evidence_preserving_merges"] == 1
