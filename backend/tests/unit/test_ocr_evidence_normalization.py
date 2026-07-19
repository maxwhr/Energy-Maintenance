from __future__ import annotations

from uuid import uuid4

from app.services.ocr_evidence_normalization_service import OcrEvidenceNormalizationService


def test_ocr_blocks_preserve_locator_and_extract_model_alarm() -> None:
    service = OcrEvidenceNormalizationService()
    media_id = uuid4()
    payload = {
        "width": 1000,
        "height": 500,
        "confidence": 0.92,
        "regions": [{
            "text": "设备型号 SUN2000-100KTL-M2 告警代码 2064 RS485 离线 2026-07-15 12:30 600V",
            "bbox": [100, 50, 900, 450],
            "confidence": 0.96,
        }],
    }

    blocks = service.normalize_blocks(payload, media_id=media_id, provider_trace_id="trace-safe")
    evidence = service.to_evidence(
        payload,
        media_id=media_id,
        ocr_result_id=uuid4(),
        provider="authorized_ocr",
        provider_model="ocr-v1",
        provider_trace_id="trace-safe",
    )

    assert blocks[0].device_models == ["SUN2000-100KTL-M2"]
    assert blocks[0].alarm_codes == ["2064"]
    assert blocks[0].bounding_box == [0.1, 0.1, 0.9, 0.9]
    assert blocks[0].parameters == ["600V"]
    assert evidence[0].observation_status == "OBSERVED"
    assert evidence[0].page_or_frame_locator["locator_type"] == "ocr_region"
    assert evidence[0].metadata_json["raw_and_normalized_preserved"] is True


def test_ocr_does_not_treat_time_or_parameter_as_alarm() -> None:
    blocks = OcrEvidenceNormalizationService().normalize_blocks(
        {"text": "页面 2026-07-15 12:30 电压 600V 电流 20A", "confidence": 0.8},
        media_id=uuid4(),
    )

    assert blocks[0].alarm_codes == []


def test_low_confidence_ocr_remains_unconfirmed() -> None:
    evidence = OcrEvidenceNormalizationService().to_evidence(
        {"text": "告警代码 2064", "confidence": 0.40},
        media_id=uuid4(),
        ocr_result_id=None,
        provider="ocr",
        provider_model=None,
        provider_trace_id=None,
    )

    assert evidence[0].observation_status == "LOW_CONFIDENCE"
    assert evidence[0].alarm_code_candidates == ["2064"]
