from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_raw_dashvector_trace_excludes_filter_and_mapping_as_root_cause() -> None:
    payload = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/dashvector_recall_trace.json").read_text(encoding="utf-8"))
    assert payload["partition"] == "pilot_r2"
    assert payload["cases"] == 40
    assert payload["raw_top50_hit"] == 9
    assert payload["post_filter_hit"] == 9
    assert payload["mapping_failures"] == payload["filter_drops"] == payload["content_mismatches"] == 0
    assert payload["vectors_exported"] is False

