from __future__ import annotations

import json
from collections import Counter

from task25b_r3_dev_r5_r5_common import OUT, now_iso, write_once


def main() -> None:
    source = OUT / "canary_iteration_1.json"
    if not source.is_file():
        raise SystemExit("Canary iteration 1 must be frozen before the one allowed calibration")
    if (OUT / "canary_iteration_2.json").exists():
        raise SystemExit("calibration is forbidden after iteration 2")
    artifact = json.loads(source.read_text(encoding="utf-8"))
    rows = artifact["rows"]
    confusions = Counter(
        f"{row.get('expected_primary_intent')}->{row.get('actual_primary_intent')}"
        for row in rows
        if row.get("expected_primary_intent") != row.get("actual_primary_intent")
    )
    payload = {
        "generated_at": now_iso(),
        "calibration_count": 1,
        "maximum_allowed": 1,
        "source_iteration": 1,
        "source_dataset_hash": artifact["dataset_hash"],
        "source_label_hash": artifact["label_hash"],
        "source_case_count": artifact["case_count"],
        "formal_data_used": False,
        "labels_changed": False,
        "cases_removed": 0,
        "knowledge_added": False,
        "vectors_modified": False,
        "case_specific_rules_added": False,
        "observed_failures": {
            "metrics": artifact["metrics"],
            "intent_confusions": dict(sorted(confusions.items())),
        },
        "calibration": {
            "intent_trigger_precedence": "procedure > prerequisite+verification > cause/action troubleshooting > configuration procedure",
            "requested_information_rules": ["plain confirmed verification", "plain causal consequence"],
            "semantic_query_count": 1,
            "rerank_weights_version": "task25b_r3_dev_r5_r5_deterministic_rerank_v2_calibrated_1",
            "rerank_weight_changes": {
                "normalized_rrf_score": [0.12, 0.35],
                "direct_answer_score": [0.20, 0.18],
                "requested_information_coverage": [0.17, 0.14],
            },
            "rerank_sort_precedence": ["protected exact grounded evidence", "final score", "direct answer", "request coverage"],
            "confidence_threshold_changed": False,
            "refinement_rule_changed": False,
        },
    }
    write_once("dev_tuning.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "observed_failures"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
