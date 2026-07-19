from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.multimodal_case import MultimodalEvidenceCreate


def payload(**overrides):
    data = {
        "modality": "VISUAL_REGION",
        "evidence_type": "INDICATOR_LIGHT",
        "source_type": "MULTIMODAL_PROVIDER",
        "source_hash": "a" * 64,
        "visual_attributes": {"color": "red", "state": "flashing_candidate"},
        "bounding_box": [0.1, 0.2, 0.5, 0.6],
        "page_or_frame_locator": {"source_image_id": "media-safe", "region_id": "region-1"},
        "indicator_state_candidates": ["red_flashing_candidate"],
        "confidence": .71,
        "observation_status": "INFERRED",
    }
    data.update(overrides)
    return data


def test_visual_evidence_preserves_region_locator_and_inference_boundary() -> None:
    item = MultimodalEvidenceCreate(**payload())
    assert item.bounding_box == [0.1, 0.2, 0.5, 0.6]
    assert item.page_or_frame_locator["region_id"] == "region-1"
    assert item.observation_status == "INFERRED"


@pytest.mark.parametrize("status", ["OBSERVED", "USER_CONFIRMED"])
def test_visual_provider_cannot_create_observed_or_confirmed_fact(status: str) -> None:
    with pytest.raises(ValidationError):
        MultimodalEvidenceCreate(**payload(observation_status=status))


def test_ocr_provider_cannot_self_confirm() -> None:
    with pytest.raises(ValidationError):
        MultimodalEvidenceCreate(**payload(
            modality="OCR_TEXT", source_type="OCR_PROVIDER", evidence_type="ALARM_CODE",
            observation_status="USER_CONFIRMED",
        ))
