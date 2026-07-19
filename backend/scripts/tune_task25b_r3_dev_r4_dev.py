from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from task25b_r3_dev_r4_common import OUT, now_iso, read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit Train/Dev tuning approval is required")
    iteration_1 = read_json(OUT / "canary_iteration_1.json")
    if not iteration_1 or iteration_1.get("iteration") != 1:
        raise SystemExit("Canary iteration 1 must be completed before tuning")
    if iteration_1.get("passed"):
        raise SystemExit("Canary iteration 1 passed; a tuning iteration is not permitted")
    if (OUT / "canary_iteration_2.json").exists():
        raise SystemExit("Canary iteration 2 already exists; further tuning is prohibited")
    if (OUT / "dev_tuning.json").exists():
        raise SystemExit("the single permitted Train/Dev tuning artifact already exists")

    missed_by_intent: dict[str, Counter] = defaultdict(Counter)
    missing = 0
    for row in iteration_1.get("rows") or []:
        if row.get("mode") != "adaptive_grounded" or not row.get("vector_heavy"):
            continue
        expected = row.get("expected_semantic_unit_id")
        if expected and expected not in (row.get("ranked_ids") or [])[:5]:
            missing += 1
            requested = row.get("requested_anchor_types") or []
            intent = str(requested[0] if requested else "UNKNOWN")
            for anchor_type in requested:
                missed_by_intent[intent][str(anchor_type)] += 1
    payload = {
        "generated_at": now_iso(), "source_iteration": 1, "test_data_used": False,
        "case_id_specific_rules": False, "source_facts_changed": False,
        "single_permitted_tuning": True, "missed_vector_heavy_at_5": missing,
        "missed_requested_anchor_types": {key: dict(value) for key, value in missed_by_intent.items()},
        "typed_consistency_step": 0.04, "primary_intent_boost": 0.035,
        "candidate_round_robin": True,
        "focus_query": True,
        "intent_anchor_overrides": {},
        "reason": "Train/Dev-only typed consistency and candidate diversity; no query, label, source, or test mutation",
        "expert_verified": False,
    }
    write_json("dev_tuning.json", payload)
    print({"status": "TRAIN_DEV_TUNED_ONCE", "missed_vector_heavy_at_5": missing,
           "candidate_round_robin": True, "test_data_used": False})


if __name__ == "__main__":
    main()
