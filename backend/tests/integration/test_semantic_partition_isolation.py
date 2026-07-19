from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_r2_and_default_partitions_remain_unchanged() -> None:
    snapshot = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/r2_snapshot.json").read_text(encoding="utf-8"))
    reconciliation = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/semantic_reconciliation.json").read_text(encoding="utf-8"))
    assert snapshot["read_only"] is True
    assert snapshot["pilot_r2_reconciliation"]["remote_partition_count"] == 1262
    assert reconciliation["pilot_r2_changed"] is False
    assert reconciliation["default_partition_changed"] is False
