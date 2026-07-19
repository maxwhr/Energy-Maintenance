from __future__ import annotations

import json

from task25b_r3_dev_r5_r5_common import DATASET_VERSION, read_json, sha256_json, sha256_file, OUT


def main() -> None:
    dataset = read_json("train_dev_dataset_v1.json")
    manifest = read_json("dataset_manifest.json")
    hashes = read_json("dataset_hash_manifest.json")
    rows = dataset["rows"]
    labels = [
        {
            "case_id": row["case_id"],
            "expected_primary_intent": row["expected_primary_intent"],
            "expected_requested_information": row["expected_requested_information"],
            "evaluation_identity": row["evaluation_identity"],
            "requires_clarification": bool(row.get("requires_clarification")),
            "no_answer": bool(row.get("no_answer")),
        }
        for row in rows
    ]
    checks = {
        "version": dataset.get("dataset_version") == DATASET_VERSION == manifest.get("dataset_version"),
        "case_count_80": len(rows) == dataset.get("case_count") == manifest.get("case_count") == 80,
        "dataset_hash": sha256_json(rows) == dataset.get("dataset_hash") == manifest.get("dataset_hash"),
        "label_hash": sha256_json(labels) == dataset.get("label_hash") == manifest.get("label_hash"),
        "file_hash": sha256_file(OUT / "train_dev_dataset_v1.json") == hashes.get("dataset_json_sha256"),
        "unique_case_ids": len({row["case_id"] for row in rows}) == len(rows),
        "unique_queries": len({row["query"] for row in rows}) == len(rows),
        "fixed_iteration_counts": hashes["iteration_contract"]["iteration_1_case_count"] == hashes["iteration_contract"]["iteration_2_case_count"] == 80,
        "fixed_iteration_hashes": hashes["iteration_contract"]["iteration_1_dataset_hash"] == hashes["iteration_contract"]["iteration_2_dataset_hash"] == dataset["dataset_hash"],
        "labels_frozen": hashes["iteration_contract"]["labels_mutable_after_iteration_start"] is False,
        "all_coverage_requirements": all(dataset["coverage_requirements"].values()),
        "no_formal_data": dataset.get("source_formal_test_used") is False,
        "expert_verified_zero": not any(row.get("expert_verified") for row in rows),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit(json.dumps({"status": "FAILED", "failed": failed}, ensure_ascii=False))
    print(json.dumps({
        "status": "PASSED",
        "dataset_version": DATASET_VERSION,
        "case_count": len(rows),
        "dataset_hash": dataset["dataset_hash"],
        "label_hash": dataset["label_hash"],
        "checks": checks,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
