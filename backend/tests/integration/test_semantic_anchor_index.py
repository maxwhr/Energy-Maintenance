from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_semantic_anchor_index_is_isolated_and_reconciled() -> None:
    index = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/semantic_anchor_index.json").read_text(encoding="utf-8"))
    reconciliation = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/semantic_reconciliation.json").read_text(encoding="utf-8"))
    assert index["partition"] == "pilot_r3_semantic"
    assert index["anchor_vectors"] == 416
    assert index["raw_partition_unchanged"] == "pilot_r2"
    assert index["raw_vector_rewrite"] is False
    assert reconciliation["passed"] is True
    assert reconciliation["missing_anchor"] == reconciliation["orphan_anchor"] == reconciliation["duplicate_anchor_id"] == 0
