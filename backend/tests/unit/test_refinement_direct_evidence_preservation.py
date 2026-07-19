from app.services.result_set_refinement_service import ResultSetRefinementService
from tests.minimax_test_helpers import candidate


def test_refinement_keeps_more_complete_direct_survivor_and_merges_sources():
    broad = candidate("broad", content="概述", rrf=.9)
    direct = candidate("direct", content="原因和处理方法", rrf=.7)
    broad.evidence_equivalence_key = direct.evidence_equivalence_key = "source-group"
    broad.direct_answer_score = .2
    direct.direct_answer_score = .9
    result = ResultSetRefinementService().refine_query_aware([broad, direct], requested_top_k=5)
    assert result.surfaced[0].candidate_id == "direct"
    assert broad.chunk_id in result.surfaced[0].source_chunk_ids
    assert result.diagnostics["relevant_candidates_lost_without_reason"] == 0
