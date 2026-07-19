import json
from pathlib import Path


def test_candidate_miss_trace_has_one_non_unknown_primary_reason():
    path = Path(__file__).parents[3] / ".runtime/task25b_r3_dev_r5_r5/candidate_miss_forensics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["total_misses"] == 17
    assert payload["unknown"] == 0
    assert all(row["primary_reason"] != "UNKNOWN" for row in payload["rows"])
