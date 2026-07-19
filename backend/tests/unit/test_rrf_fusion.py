from app.services.rrf_fusion_service import QueryAwareCandidate, RRFFusionService


def candidate(value: str, channel: str, *, exact: bool = False):
    return QueryAwareCandidate(
        candidate_id=value,
        chunk_id=value,
        document_id="doc",
        document_title="manual",
        content="evidence",
        source_channels={channel},
        source_query_types={"ORIGINAL"},
        exact_model_match=exact,
        scope_validation_passed=True,
    )


def test_rrf_deduplicates_votes_and_merges_channels() -> None:
    first = candidate("a", "SCOPED_KEYWORD")
    duplicate_in_vote = candidate("a", "SCOPED_KEYWORD")
    semantic = candidate("a", "SEMANTIC_UNIT")
    other = candidate("b", "SCOPED_KEYWORD")
    result = RRFFusionService().fuse({"keyword": [first, duplicate_in_vote, other], "semantic": [semantic]})
    assert [item.candidate_id for item in result].count("a") == 1
    assert result[0].source_channels == {"SCOPED_KEYWORD", "SEMANTIC_UNIT"}
    assert result[0].scope_validation_passed is True


def test_exact_boost_is_bounded_but_effective() -> None:
    exact = candidate("exact", "EXACT_KEYWORD", exact=True)
    ordinary = candidate("ordinary", "SCOPED_KEYWORD")
    result = RRFFusionService().fuse({"one": [ordinary], "two": [exact]})
    assert result[0].candidate_id == "exact"
