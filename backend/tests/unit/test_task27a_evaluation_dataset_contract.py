from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


DATASET_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "task27a_huawei_sun2000_engineering_candidate_v1.json"
EXPECTED_COMPOSITION = {
    "manufacturer_model": 5,
    "alarm_code": 5,
    "insulation": 4,
    "communication": 4,
    "temperature_heat": 3,
    "grid_connection": 3,
    "dc_input_mppt": 2,
    "safety_high_risk": 2,
    "no_data_out_of_scope": 2,
}


def test_task27a_dataset_is_frozen_engineering_candidate_with_exact_composition() -> None:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert payload["status"] == "ENGINEERING_CANDIDATE"
    assert payload["expert_reviewed"] is False
    assert payload["expert_quality_gate"] == "BLOCKED_PENDING_HUMAN_REVIEW"
    assert len(cases) == 30
    assert dict(Counter(item["category"] for item in cases)) == EXPECTED_COMPOSITION
    assert len({item["case_id"] for item in cases}) == 30
    assert all(item["review_status"] == "engineering_candidate" for item in cases)
    assert all(item["expert_reviewed"] is False for item in cases)


def test_task27a_dataset_uses_real_ids_only_for_answerable_cases() -> None:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))

    for item in payload["cases"]:
        if item["should_abstain"]:
            assert item["expected_document_ids"] == []
            assert item["expected_chunk_ids"] == []
        else:
            assert item["expected_document_ids"]
            assert item["expected_chunk_ids"]
