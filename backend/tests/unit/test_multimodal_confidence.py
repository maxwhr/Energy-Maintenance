from app.services.multimodal_confidence_service import MultimodalConfidenceService
from app.services.multimodal_evidence_fusion_service import FusedEvidence, MultimodalEvidenceFusion


def test_open_high_conflict_prevents_high_confidence() -> None:
    fusion = MultimodalEvidenceFusion(confirmed=[FusedEvidence(
        evidence_id="e1", level="CONFIRMED", evidence_type="DEVICE_MODEL", value="SUN2000",
        confidence=1.0, source_type="USER_INPUT", media_id=None, locator={},
    )])

    result = MultimodalConfidenceService().calculate(
        fusion,
        valid_citation_count=3,
        open_high_conflicts=1,
        required_missing_count=0,
    )

    assert result.status == "CONFLICTED"
    assert result.score < 0.75
