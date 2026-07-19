from app.services.minimax_tiebreak_service import CandidateTieBreakPatch, MiniMaxTieBreakService


def test_unknown_and_duplicate_candidate_ids_are_rejected() -> None:
    unknown = CandidateTieBreakPatch.model_validate({
        "ordered_candidate_ids": ["c2"],
        "scores": [{"candidate_id": "c2", "support": 1, "intent_match": 1, "contradiction": False}],
        "needs_clarification": False,
    })
    assert MiniMaxTieBreakService._validate_boundary(unknown, {"c0", "c1"}) == "UNKNOWN_CANDIDATE_ID"
    duplicate = CandidateTieBreakPatch.model_validate({
        "ordered_candidate_ids": ["c0", "c0"],
        "scores": [{"candidate_id": "c0", "support": 1, "intent_match": 1, "contradiction": False}],
        "needs_clarification": False,
    })
    assert MiniMaxTieBreakService._validate_boundary(duplicate, {"c0", "c1"}) == "DUPLICATE_CANDIDATE_ID"
