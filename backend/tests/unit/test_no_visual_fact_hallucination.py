from __future__ import annotations

from uuid import uuid4

from app.services.visual_signal_extraction_service import VisualSignalExtractionService


def test_provider_model_and_alarm_guesses_are_suppressed_from_evidence() -> None:
    evidence = VisualSignalExtractionService().to_evidence(
        {
            "observations": ["设备外观候选"],
            "regions": [{"bbox": [0, 0, 1, 1], "region_type": "general", "confidence": 0.9}],
            "device_model": "SUN2000-NOT-VISIBLE",
            "alarm_codes": ["999999"],
            "confidence": 0.9,
        },
        media_id=uuid4(),
        analysis_id=None,
    )

    assert evidence[0].device_model_candidates == []
    assert evidence[0].alarm_code_candidates == []
    assert evidence[0].metadata_json["device_model_candidates_suppressed"] is True
    assert evidence[0].metadata_json["alarm_code_candidates_suppressed"] is True
