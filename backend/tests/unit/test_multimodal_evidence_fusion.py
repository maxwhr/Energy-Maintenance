from __future__ import annotations

from types import SimpleNamespace

from app.services.multimodal_evidence_fusion_service import MultimodalEvidenceFusionService


def _item(evidence_id: str, **overrides):
    values = {
        "evidence_id": evidence_id,
        "observation_status": "OBSERVED",
        "contradicted": False,
        "normalized_text": "value",
        "observed_text": "value",
        "evidence_type": "GENERAL_OBSERVATION",
        "confidence": 0.8,
        "source_type": "OCR_PROVIDER",
        "media_id": None,
        "region_id": None,
        "page_or_frame_locator": {"line": 1},
        "user_confirmed": False,
        "metadata_json": {},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_fusion_does_not_promote_visual_inference() -> None:
    fusion = MultimodalEvidenceFusionService().fuse([
        _item("visual", source_type="MULTIMODAL_PROVIDER", observation_status="INFERRED", confidence=0.95),
        _item("user", user_confirmed=True, observation_status="USER_CONFIRMED", normalized_text="confirmed"),
        _item("knowledge", source_type="OFFICIAL_KNOWLEDGE", normalized_text="manual", evidence_type="SCREEN_TEXT"),
    ])

    assert [item.evidence_id for item in fusion.inferred] == ["visual"]
    assert [item.evidence_id for item in fusion.confirmed] == ["user"]
    assert [item.evidence_id for item in fusion.knowledge_supported] == ["knowledge"]


def test_high_confidence_ocr_requires_official_match_for_confirmed_level() -> None:
    without_match = MultimodalEvidenceFusionService().fuse([
        _item("ocr", evidence_type="ALARM_CODE", confidence=0.96),
    ])
    with_match = MultimodalEvidenceFusionService().fuse([
        _item("ocr2", evidence_type="ALARM_CODE", confidence=0.96, metadata_json={"official_match_valid": True}),
    ])

    assert [item.evidence_id for item in without_match.observed] == ["ocr"]
    assert [item.evidence_id for item in with_match.confirmed] == ["ocr2"]
