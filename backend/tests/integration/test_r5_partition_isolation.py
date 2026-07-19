import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_r5_reconciliation_preserves_all_historical_partitions() -> None:
    payload = json.loads((ROOT / ".runtime/task25b_r3_dev_r5/reconciliation.json").read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["old_partition_counts"] == {
        "pilot_r2": 1262,
        "pilot_r3_semantic": 416,
        "pilot_r4_grounded": 1289,
    }
    assert payload["default_partition_affected"] is False
    assert payload["original_vectors_reindexed"] == 0
