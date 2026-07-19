from __future__ import annotations

from types import SimpleNamespace

from app.services.multimodal_evidence_conflict_service import MultimodalEvidenceConflictService


def _item(evidence_id: str, **overrides):
    values = {
        "evidence_id": evidence_id,
        "observation_status": "OBSERVED",
        "confidence": 0.9,
        "user_confirmed": False,
        "device_model_candidates": [],
        "alarm_code_candidates": [],
        "indicator_state_candidates": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_model_conflict_has_stable_identity_and_question() -> None:
    service = MultimodalEvidenceConflictService()
    items = [
        _item("e-user", user_confirmed=True, observation_status="USER_CONFIRMED", device_model_candidates=["SUN2000-100KTL-M2"]),
        _item("e-ocr", device_model_candidates=["SUN2000-50KTL-M3"]),
    ]

    first = service.detect(items)
    second = service.detect(items)

    assert first[0].conflict_type == "DEVICE_MODEL_CONFLICT"
    assert first[0].severity == "HIGH"
    assert first[0].conflict_id == second[0].conflict_id
    assert "确认" in first[0].recommended_question


def test_multiple_unconfirmed_alarms_are_not_assumed_conflicting() -> None:
    conflicts = MultimodalEvidenceConflictService().detect([
        _item("e1", alarm_code_candidates=["2064"]),
        _item("e2", alarm_code_candidates=["2065"]),
    ])

    assert conflicts == []
