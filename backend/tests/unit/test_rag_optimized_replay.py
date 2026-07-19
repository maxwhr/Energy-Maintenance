from app.services.rag_compatibility_replay_service import RagCompatibilityReplayService
from tests.unit.test_rag_sequential_reference import CONTEXT


def test_optimized_replay_never_calls_provider_for_clarification_only_case():
    result = RagCompatibilityReplayService(None).replay(
        context=CONTEXT, snapshots=[], mode="OPTIMIZED_REPLAY"
    )
    assert result.output["confidence_status"] == "NEEDS_CLARIFICATION"
    assert result.diagnostics["embedding_calls"] == 0
