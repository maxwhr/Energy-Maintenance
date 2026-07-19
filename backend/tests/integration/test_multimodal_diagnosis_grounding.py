from __future__ import annotations

from app.services.multimodal_diagnosis_service import MultimodalDiagnosisService
from app.services.multimodal_entity_resolution_service import MultimodalEntityResolution
from app.services.multimodal_evidence_fusion_service import FusedEvidence, MultimodalEvidenceFusion
from app.services.multimodal_safety_guard_service import MultimodalSafetyDecision


def test_diagnosis_abstains_without_valid_official_citation() -> None:
    result = MultimodalDiagnosisService().build(
        case_id="mmc_test",
        resolution=MultimodalEntityResolution(
            resolved_device_model="SUN2000",
            resolved_alarm_codes=["2064"],
        ),
        fusion=MultimodalEvidenceFusion(observed=[FusedEvidence(
            evidence_id="e1", level="OBSERVED", evidence_type="ALARM_CODE", value="2064",
            confidence=0.9, source_type="OCR_PROVIDER", media_id=None, locator={"line": 1},
        )]),
        citations=[],
        safety=MultimodalSafetyDecision(
            safety_level="NORMAL", stop_required=False, professional_required=False,
            safety_warnings=["遵循现场安全制度。"],
        ),
    )

    assert result.possible_faults == []
    assert result.confidence_status == "INSUFFICIENT_EVIDENCE"
    assert result.unsupported_diagnosis_count == 0
    assert "valid_official_citation" in result.missing_information
