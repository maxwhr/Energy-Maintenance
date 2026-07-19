from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_grounding_audit_preserves_weak_and_ambiguous_cases() -> None:
    payload = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/vector_heavy_grounding.json").read_text(encoding="utf-8"))
    assert payload["test_v3_used"] is False
    assert payload["cases_reviewed"] == 88
    assert payload["summary"] == {"AMBIGUOUS_SECTION": 19, "GROUNDED_STRONG": 29, "GROUNDING_WEAK": 40}
    assert payload["usable_canary_cases"] == 29

