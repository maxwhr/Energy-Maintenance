import json
from pathlib import Path


def test_fixed_canary_contract_is_80_cases_and_iteration_hashes_match():
    base = Path(__file__).parents[3] / ".runtime/task25b_r3_dev_r5_r5"
    dataset = json.loads((base / "train_dev_dataset_v1.json").read_text(encoding="utf-8"))
    hashes = json.loads((base / "dataset_hash_manifest.json").read_text(encoding="utf-8"))
    contract = hashes["iteration_contract"]
    assert dataset["case_count"] == 80
    assert contract["iteration_1_case_count"] == contract["iteration_2_case_count"] == 80
    assert contract["iteration_1_dataset_hash"] == contract["iteration_2_dataset_hash"] == dataset["dataset_hash"]
