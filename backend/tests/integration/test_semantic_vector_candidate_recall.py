from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_semantic_candidate_recall_failure_is_preserved_as_a_stop_gate() -> None:
    payload = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/canary_result.json").read_text(encoding="utf-8"))
    assert payload["vector_heavy"]["candidate_recall_at_50"] == 0.444444
    assert payload["checks"]["semantic_candidate_recall_at_50"] is False
    assert payload["status"] == "CANARY_FAILED"

