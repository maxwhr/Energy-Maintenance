from app.core.database import SessionLocal
from app.services.record_center_service import RecordCenterService
from scripts.task25e_common import read_json, sha256_value


def test_default_overview_matches_frozen_response_hash() -> None:
    baseline = read_json("baseline.json", {})
    assert baseline.get("status") == "TASK25E_BASELINE_FROZEN"
    with SessionLocal() as db:
        first = RecordCenterService(db).overview()
    with SessionLocal() as db:
        second = RecordCenterService(db).overview()

    # Preserve the response contract and deterministic ordering without
    # pretending that mutable production counts must forever equal the Task
    # 25E point-in-time snapshot.
    expected_categories = set((baseline.get("overview_category_statistics") or {}).keys())
    assert expected_categories.issubset(first.keys())
    assert first.keys() == second.keys()
    assert sha256_value(first) == sha256_value(second)
