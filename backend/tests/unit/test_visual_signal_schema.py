from __future__ import annotations

from uuid import uuid4

from app.services.visual_signal_extraction_service import VisualSignalExtractionService


def test_visual_signal_keeps_only_observable_region_data() -> None:
    payload = {
        "observations": ["可见红色指示灯"],
        "regions": [{
            "region_id": "light-1",
            "bbox": [0.1, 0.2, 0.3, 0.4],
            "region_type": "indicator",
            "text": "红灯候选",
            "attributes": {"color": "red", "state": "blinking", "internal_fault": "made-up"},
            "confidence": 0.86,
        }],
        "candidate_device_type": "pv_inverter",
        "candidate_components": ["indicator", "unsupported internal board"],
        "indicator_states": [{"color": "red", "state": "blinking", "confidence": 0.84}],
        "confidence": 0.88,
        "diagnosis": "确定内部器件损坏",
        "alarm_codes": ["2064"],
        "device_model": "SUN2000-FAKE",
    }

    result = VisualSignalExtractionService().normalize(payload)
    evidence = VisualSignalExtractionService().to_evidence(payload, media_id=uuid4(), analysis_id=None)

    assert result.regions[0].attributes == {"color": "red", "state": "blinking"}
    assert result.candidate_components == ["indicator"]
    assert {"diagnosis", "alarm_codes", "device_model"}.issubset(result.unsupported_fields_removed)
    assert evidence[0].observation_status == "INFERRED"
    assert evidence[0].device_model_candidates == []
    assert evidence[0].alarm_code_candidates == []
    assert evidence[0].page_or_frame_locator["locator_type"] == "visual_region"


def test_visual_signal_low_confidence_never_becomes_observed() -> None:
    evidence = VisualSignalExtractionService().to_evidence(
        {
            "observations": ["可能有积尘"],
            "regions": [{"bbox": [0, 0, 1, 1], "region_type": "damage", "text": "积尘", "confidence": 0.4}],
            "confidence": 0.4,
        },
        media_id=uuid4(),
        analysis_id=None,
    )

    assert evidence[0].observation_status == "LOW_CONFIDENCE"
    assert evidence[0].source_type == "MULTIMODAL_PROVIDER"
