from app.services.deterministic_evidence_rerank_service import DeterministicEvidenceRerankService
from tests.minimax_test_helpers import minimax_settings


def test_minimax_standard_tier_and_weights_contract() -> None:
    settings = minimax_settings()
    assert settings.MINIMAX_SERVICE_TIER == "standard"
    assert settings.MINIMAX_THINKING_TYPE == "disabled"
    assert settings.RAG_REQUEST_LEVEL_PROVIDER_FALLBACK_ENABLED is False
    assert sum(DeterministicEvidenceRerankService(settings).weights.values()) == 1.0
