from __future__ import annotations

import json
from copy import deepcopy

from task25b_r3_dev_r5_r6_common import (
    DATASET_VERSION,
    OUT,
    SOURCE,
    now_iso,
    sha256_file,
    sha256_json,
    write_json,
)


LABEL_FIELDS = (
    "query", "category", "no_answer", "requires_clarification", "expected_primary_intent",
    "expected_requested_information", "expected_device_models", "expected_alarm_codes", "evaluation_identity",
)


def label_payload(rows: list[dict]) -> list[dict]:
    return [{key: row.get(key) for key in LABEL_FIELDS} for row in rows]


def main() -> None:
    probe_path = OUT / "qwen_rerank_probe.json"
    if not probe_path.is_file() or json.loads(probe_path.read_text(encoding="utf-8")).get("status") != "QWEN3_RERANK_PROBE_PASSED":
        raise SystemExit("Qwen3 Probe must pass before freezing R5-R6 Train/Dev")
    source_path = SOURCE / "train_dev_dataset_v1.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    rows = deepcopy(source.get("rows") or [])
    if len(rows) != 80:
        raise SystemExit(f"expected exactly 80 inherited frozen cases, got {len(rows)}")
    mapping = []
    for index, row in enumerate(rows, start=1):
        old_id = str(row["case_id"])
        new_id = f"r5r6-{index:03d}-{old_id.split('-')[-1]}"
        mapping.append({"old_case_id": old_id, "new_case_id": new_id})
        row["case_id"] = new_id
        row["dataset_version"] = DATASET_VERSION
        row["label_version"] = DATASET_VERSION
    source_label_hash = sha256_json(label_payload(source.get("rows") or []))
    target_label_hash = sha256_json(label_payload(rows))
    # case_id and version are deliberately excluded from the label payload.
    labels_unchanged = source_label_hash == target_label_hash
    dataset = {
        "generated_at": now_iso(),
        "dataset_version": DATASET_VERSION,
        "case_count": len(rows),
        "source_dataset": source.get("dataset_version"),
        "source_dataset_sha256": sha256_file(source_path),
        "source_formal_test_used": False,
        "immutable_after_creation": True,
        "labels_unchanged": labels_unchanged,
        "source_label_hash": source_label_hash,
        "label_hash": target_label_hash,
        "old_to_new_mapping": mapping,
        "rows": rows,
    }
    dataset["dataset_hash"] = sha256_json({key: value for key, value in dataset.items() if key != "dataset_hash"})
    manifest = {
        "dataset_version": DATASET_VERSION,
        "dataset_hash": dataset["dataset_hash"],
        "label_hash": target_label_hash,
        "source_label_hash": source_label_hash,
        "labels_unchanged": labels_unchanged,
        "case_count": len(rows),
        "mapping_count": len(mapping),
        "source_dataset": source.get("dataset_version"),
        "formal_overlap": 0,
        "expert_verified": False,
    }
    write_json("train_dev_dataset_v1.json", dataset, immutable=True)
    write_json("dataset_manifest.json", manifest, immutable=True)
    write_json("dataset_hash_manifest.json", {
        "algorithm": "sha256", "dataset_hash": dataset["dataset_hash"], "label_hash": target_label_hash,
        "source_dataset_sha256": sha256_file(source_path), "generated_at": now_iso(),
    }, immutable=True)
    write_json("old_to_new_case_mapping.json", {"mapping": mapping}, immutable=True)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
