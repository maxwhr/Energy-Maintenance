from app.services.rag_compatibility_replay_service import RagCompatibilityReplayService


CONTEXT = {
    "case_id": "clarification-case",
    "reference_output": {
        "query_understanding_hash": "u", "query_variant_hashes": [], "requested_channels": [],
        "confidence_status": "NEEDS_CLARIFICATION", "no_answer": False, "needs_clarification": True,
    },
}


def test_sequential_reference_never_calls_provider_for_clarification_only_case():
    result = RagCompatibilityReplayService(None).replay(
        context=CONTEXT, snapshots=[], mode="SEQUENTIAL_REFERENCE"
    )
    assert result.output["needs_clarification"] is True
    assert result.output["candidate_identities"] == []
    assert result.diagnostics["provider_calls"] == 0
