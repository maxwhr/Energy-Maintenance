from app.services.rrf_fusion_service import QueryAwareCandidate, RRFFusionService


def candidate(candidate_id: str, channel: str) -> QueryAwareCandidate:
    return QueryAwareCandidate(
        candidate_id=candidate_id,
        chunk_id=candidate_id,
        document_id="d1",
        document_title="doc",
        content="same",
        source_channels={channel},
        source_query_types={"ORIGINAL"},
        source_chunk_ids=[candidate_id],
        scope_validation_passed=True,
    )


def test_rrf_ties_do_not_depend_on_ranking_dictionary_order():
    first = {
        "RAW_VECTOR:ORIGINAL:v1": [candidate("b", "RAW_VECTOR")],
        "EXACT_KEYWORD:ORIGINAL:v1": [candidate("a", "EXACT_KEYWORD")],
    }
    second = dict(reversed(list(first.items())))
    left = [item.candidate_id for item in RRFFusionService(exact_boost=0, consistency_boost=0).fuse(first)]
    right = [item.candidate_id for item in RRFFusionService(exact_boost=0, consistency_boost=0).fuse(second)]
    assert left == right == ["a", "b"]
