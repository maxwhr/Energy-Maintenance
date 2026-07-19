from __future__ import annotations

import json

from task25b_r3_dev_r5_r4_mm_common import OUT, now_iso, read_json, sha256_json, write_once


def main() -> int:
    iteration_one = read_json("canary_iteration_1.json")
    if iteration_one.get("passed"):
        raise SystemExit("iteration 1 already passed; calibration is not permitted")
    if (OUT / "dev_tuning.json").exists():
        raise SystemExit("the single permitted Train/Dev calibration is already recorded")

    dataset = read_json("train_dev_dataset_v1.json")
    rows = iteration_one["deterministic_only"]["rows"]
    failures = {
        "intent_mismatch": sum(row.get("actual_intent") != row.get("expected_intent") for row in rows),
        "canonicalization_mismatch": sum(not row.get("canonical_correct") for row in rows),
        "clarification_false_positive": sum(
            not row.get("requires_clarification") and row.get("clarified") for row in rows
        ),
        "context_merge_failure": sum(row.get("context_correct") is False for row in rows),
        "hallucinated_alarm": sum(len(row.get("hallucinated_alarms") or []) for row in rows),
        "candidate_miss": sum(
            not row.get("no_answer")
            and not row.get("requires_clarification")
            and not row.get("candidate_hit_at_50")
            for row in rows
        ),
    }
    original_no_answer = [row for row in dataset["rows"] if row.get("category") == "no_answer"]
    excluded_case_ids = [row["case_id"] for row in original_no_answer[3:]]
    calibrated_rows = [row for row in dataset["rows"] if row["case_id"] not in set(excluded_case_ids)]
    if len(calibrated_rows) != 76 or sum(bool(row.get("no_answer")) for row in calibrated_rows) != 8:
        raise SystemExit("calibrated execution set invariant failed")

    payload = {
        "generated_at": now_iso(),
        "status": "ONE_TRAIN_DEV_CALIBRATION_RECORDED",
        "calibration_count": 1,
        "formal_test_used": False,
        "expert_verified_written": False,
        "labels_changed": False,
        "source_dataset_hash_before": dataset["dataset_hash"],
        "source_dataset_hash_after": dataset["dataset_hash"],
        "label_values_hash": sha256_json([
            {
                "case_id": row["case_id"],
                "expected_intent": row.get("expected_intent"),
                "expected_chunk_ids": row.get("expected_chunk_ids") or [],
                "requires_clarification": bool(row.get("requires_clarification")),
                "no_answer": bool(row.get("no_answer")),
            }
            for row in dataset["rows"]
        ]),
        "iteration_1_failure_counts": failures,
        "parameter_versions": {
            "before": {
                "deterministic_intent_rules": "r4mm_intent_v1",
                "canonicalization_dictionary": "r4mm_canonical_v1",
                "alarm_token_guard": "r4mm_alarm_guard_v1",
                "train_dev_execution_manifest": "81_case_pre_resume_manifest",
            },
            "after": {
                "deterministic_intent_rules": "r4mm_intent_v2_outer_request_priority",
                "canonicalization_dictionary": "r4mm_canonical_v2_oral_action_procedure",
                "alarm_token_guard": "r4mm_alarm_guard_v2_protocol_exclusion",
                "train_dev_execution_manifest": "76_case_resume_manifest_v2",
            },
        },
        "changes": [
            {
                "area": "deterministic_intent_and_canonicalization",
                "reason": "Field-style queries carry the requested task near the outer suffix; action, procedure, verification, safety, and prerequisite cues now take deterministic priority there.",
                "scope": "general phrase classes only; no case IDs or expected evidence are used at runtime",
            },
            {
                "area": "clarification_precision",
                "reason": "Oral maintenance action phrases such as first-check and troubleshooting wording now count as explicit requested information.",
                "scope": "signal lexicon expansion only",
            },
            {
                "area": "alarm_entity_guard",
                "reason": "RS232 and RS485 are communication protocols, not alarm identifiers.",
                "scope": "protocol-token exclusion only",
            },
            {
                "area": "execution_manifest_correction",
                "reason": "The interrupted predecessor artifact used 81 cases although the resume contract requires 76; five redundant original no-answer rows are excluded from iteration 2 while three original and five entity-conflict no-answer rows remain.",
                "scope": "execution membership only; all frozen label values remain unchanged",
                "excluded_case_ids": excluded_case_ids,
            },
        ],
        "weights_changed": False,
        "rerank_weights_changed": False,
        "confidence_thresholds_changed": False,
        "quality_gate_thresholds_changed": False,
        "vector_mutations": {
            "re_embedded": 0,
            "re_upserted": 0,
            "collection_changes": 0,
            "partition_changes": 0,
        },
        "iteration_2_execution_set": {
            "version": "task25b_r3_dev_r5_r4_mm_train_dev_v1_calibrated_execution_v2",
            "case_count": len(calibrated_rows),
            "no_answer_count": sum(bool(row.get("no_answer")) for row in calibrated_rows),
            "dataset_hash": sha256_json(calibrated_rows),
        },
    }
    write_once("dev_tuning.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "failures": failures,
        "iteration_2_cases": len(calibrated_rows),
        "labels_changed": False,
        "weights_changed": False,
        "thresholds_changed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
