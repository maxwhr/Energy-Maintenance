from app.services.rag_compatibility_diff_service import RagCompatibilityDiffService
from app.services.rag_compatibility_replay_service import RagReplayResult


def replay(mode: str, rrf):
    stages = {
        "QUERY_UNDERSTANDING": "u", "QUERY_VARIANTS": [], "CHANNEL_REQUEST": [],
        "CHANNEL_RAW_RESULT": [], "CHANNEL_NORMALIZATION": {}, "CANDIDATE_MAPPING": {},
        "EVIDENCE_IDENTITY": {}, "DEDUP": {}, "RRF": rrf, "DETERMINISTIC_RERANK": rrf,
        "POST_GUARD": rrf, "REFINEMENT": rrf, "HYDRATION": [], "CITATION": [],
        "CONFIDENCE": {"status": "ANSWERABLE"}, "SERIALIZATION": {"rerank_order": rrf},
    }
    return RagReplayResult("case", mode, {"rerank_order": rrf}, stages, {})


def test_diff_reports_first_divergent_stage_not_only_final_output():
    diff = RagCompatibilityDiffService().compare(
        replay("SEQUENTIAL_REFERENCE", ["a", "b"]), replay("OPTIMIZED_REPLAY", ["b", "a"])
    )
    assert diff["first_divergent_stage"] == "RRF"
    assert diff["reason"] == "UNSTABLE_TIE_BREAK"
    assert diff["fix_required"] is True
