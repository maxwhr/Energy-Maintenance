from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_relative_gain_does_not_override_failed_semantic_quality_gates() -> None:
    payload = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/canary_result.json").read_text(encoding="utf-8"))
    vector_heavy = payload["vector_heavy"]
    assert vector_heavy["relative_recall_gain"] >= 0.10
    assert payload["checks"]["relative_semantic_gain"] is True
    assert payload["checks"]["adaptive_semantic_recall_at_5"] is False
    assert payload["checks"]["adaptive_semantic_mrr"] is False
    assert payload["checks"]["adaptive_semantic_ndcg"] is False

