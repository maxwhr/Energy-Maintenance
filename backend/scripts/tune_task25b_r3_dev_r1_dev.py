from __future__ import annotations

import argparse
import json

from task25b_r3_dev_common import ROOT, now_iso


OUT = ROOT / ".runtime" / "task25b_r3_dev_r1"


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("explicit real API approval required")
    canary = json.loads((OUT / "canary_result.json").read_text(encoding="utf-8"))
    keyword = json.loads((OUT / "keyword_path.json").read_text(encoding="utf-8"))
    if not canary.get("passed"):
        raise SystemExit("CANARY_FAILED: tuning snapshot cannot be finalized")
    payload = {
        "generated_at": now_iso(), "tuning_split": "train+dev", "test_v2_used_for_tuning": False,
        "changes": {
            "scope": "chinese_engineering_pilot_r2", "keyword_candidate_limit": 100,
            "boilerplate_ngrams_removed": True, "exact_heading_boost": 80.0,
            "vector_top_k_canary": 50, "vector_exact_anchor": True,
            "query_embedding_cache": True, "http_keep_alive": True,
            "vector_timeout_seconds": 3.5,
        },
        "dev_keyword": {key: keyword.get(key) for key in ("recall_at_5", "mrr", "p95_ms", "external_api_call_count")},
        "canary_status": canary.get("status"), "quality_thresholds_lowered": False,
        "expected_labels_used_in_runtime_rules": False,
    }
    (OUT / "dev_tuning_snapshot.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "tuning_split": "train+dev", "test_v2_used": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
