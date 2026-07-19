from __future__ import annotations

from types import SimpleNamespace

from app.services.multimodal_entity_resolution_service import MultimodalEntityResolutionService


def _case(**overrides):
    base = {
        "user_confirmed_facts": {},
        "device_model": None,
        "equipment_category": None,
        "reported_symptoms": [],
        "occurrence_conditions": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _evidence(evidence_id: str, **overrides):
    base = {
        "evidence_id": evidence_id,
        "observation_status": "OBSERVED",
        "contradicted": False,
        "user_confirmed": False,
        "source_type": "OCR_PROVIDER",
        "evidence_type": "DEVICE_MODEL",
        "confidence": 0.95,
        "device_model_candidates": [],
        "alarm_code_candidates": [],
        "component_candidates": [],
        "metadata_json": {},
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_user_confirmed_model_wins_and_conflict_is_not_silent() -> None:
    result = MultimodalEntityResolutionService().resolve(
        _case(user_confirmed_facts={"e1": {"evidence_type": "DEVICE_MODEL", "value": "SUN2000-100KTL-M2"}}),
        [_evidence("ocr-1", device_model_candidates=["SUN2000-50KTL-M3"])],
    )

    assert result.resolved_device_model == "SUN2000-100KTL-M2"
    assert result.resolved_product_family == "SUN2000"
    assert result.conflicts[0]["entity_type"] == "device_model"
    assert "conflict_resolution" in result.missing_information


def test_no_default_equipment_category_when_evidence_is_missing() -> None:
    result = MultimodalEntityResolutionService().resolve(_case(reported_symptoms=["离线"]), [])

    assert result.resolved_equipment_category is None
    assert result.resolved_device_model is None
    assert "device_model" in result.missing_information


def test_confirmed_alarm_is_not_overridden_by_ocr() -> None:
    result = MultimodalEntityResolutionService().resolve(
        _case(),
        [
            _evidence(
                "user-alarm",
                evidence_type="ALARM_CODE",
                user_confirmed=True,
                observation_status="USER_CONFIRMED",
                alarm_code_candidates=["2064"],
            ),
            _evidence("ocr-alarm", evidence_type="ALARM_CODE", alarm_code_candidates=["2065"]),
        ],
    )

    assert result.resolved_alarm_codes == ["2064"]
    assert any(item["entity_type"] == "alarm_code" for item in result.conflicts)
