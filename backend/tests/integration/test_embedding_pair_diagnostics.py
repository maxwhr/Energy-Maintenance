from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_embedding_pair_diagnostics_are_train_dev_only_and_show_dilution() -> None:
    payload = json.loads((ROOT / ".runtime/task25b_r3_dev_r3/embedding_pair_diagnostics.json").read_text(encoding="utf-8"))
    assert payload["pairs"] == 40
    assert payload["test_v3_used"] is False
    assert payload["vectors_exported"] is False
    assert payload["primary_diagnosis"] == "RAW_CHUNK_REPRESENTATION_DILUTION"
    assert payload["averages"]["query_to_semantic_text_similarity"] > payload["averages"]["query_to_raw_chunk_similarity"]

