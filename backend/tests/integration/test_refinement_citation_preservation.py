from app.services.result_set_refinement_service import ResultSetRefinementService
from tests.unit.test_refinement_evidence_preservation import _c


def test_refinement_preserves_all_citation_source_ids():
    result = ResultSetRefinementService().refine_query_aware([_c("a", "c1"), _c("b", "c2")], requested_top_k=5)
    assert set(result.surfaced[0].source_chunk_ids) == {"c1", "c2"}
