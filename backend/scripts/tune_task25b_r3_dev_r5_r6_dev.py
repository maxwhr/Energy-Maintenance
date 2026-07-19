from __future__ import annotations

import json

from task25b_r3_dev_r5_r6_common import OUT, now_iso, write_json


def main() -> None:
    if (OUT / "dev_tuning.json").exists():
        raise SystemExit("the single R5-R6 Train/Dev adjustment has already been consumed")
    source = OUT / "canary_iteration_1.json"
    if not source.is_file():
        raise SystemExit("iteration 1 is required before the one allowed adjustment")
    canary = json.loads(source.read_text(encoding="utf-8"))
    if canary.get("passed"):
        decision = "NO_ADJUSTMENT_NEEDED"
    else:
        decision = "REVIEW_RERANK_TEXT_AND_INSTRUCT_ONLY"
    payload = {
        "generated_at": now_iso(), "status": decision, "adjustment_count": 0 if canary.get("passed") else 1,
        "allowed_scope": ["rerank_text", "instruct", "top_n", "generic_post_constraints"],
        "forbidden": ["vector", "corpus", "labels", "expected_ids", "case_specific_rules"],
        "code_changed_by_script": False, "requires_human_implementation_review": not bool(canary.get("passed")),
    }
    write_json("dev_tuning.json", payload, immutable=True)
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
