from __future__ import annotations

from create_task25b_r3_dev_r5_train_dev import create_dataset
from task25b_r3_dev_r5_common import (
    OUT,
    R5_TRAIN_DEV_TUNED_VERSION,
    now_iso,
    read_json,
    write_json,
)


def main() -> None:
    first = read_json(OUT / "canary_iteration_1.json")
    if not first or first.get("iteration") != 1 or first.get("passed"):
        raise SystemExit("a failed immutable Canary iteration 1 is required before Dev tuning")
    if (OUT / "dev_tuning.json").exists() or (OUT / "train_dev_dataset_v2.json").exists():
        raise SystemExit("the single R5 Dev tuning operation has already been used")

    payload = create_dataset(
        destination_name="train_dev_dataset_v2.json",
        manifest_name="train_dev_manifest_v2.json",
        dataset_version=R5_TRAIN_DEV_TUNED_VERSION,
    )
    tuning = {
        "generated_at": now_iso(),
        "source_canary_iteration": 1,
        "source_canary_hash": first.get("dataset_hash"),
        "tuned_dataset_version": payload["dataset_version"],
        "tuned_dataset_hash": payload["dataset_hash"],
        "thresholds_changed": False,
        "formal_test_used": False,
        "changes": [
            "replace generic model/title-only generated queries with source-span-specific queries",
            "derive clarification intent from explicit request wording while retaining clarification as the expected boundary",
            "recognize explicit Chinese alarm names deterministically and route them through the exact fast path",
            "limit vector channels to original/canonical variants while retaining keyword multi-query and RRF",
            "restrict conditional rerank to cross-document candidates with a genuinely narrow RRF margin",
            "measure Fast Path from actual retrieval plans and multi-query latency before rerank/finalization",
        ],
        "iteration_limit": 2,
        "next_permitted_iteration": 2,
    }
    write_json("dev_tuning.json", tuning)
    print({
        "status": "DEV_TUNING_APPLIED_ONCE",
        "dataset_version": payload["dataset_version"],
        "cases": payload["cases"],
        "sha256": payload["dataset_hash"],
        "thresholds_changed": False,
    })


if __name__ == "__main__":
    main()
