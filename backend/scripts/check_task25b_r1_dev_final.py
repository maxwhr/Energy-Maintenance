from __future__ import annotations

from task25b_r1_common import now_iso, write_json
from task25b_r1_eval_common import evaluate_split


def main() -> int:
    evaluation = evaluate_split(split="dev", modes=["keyword", "adaptive"], allow_blind=False)
    keyword = evaluation["by_mode"]["keyword"]
    adaptive = evaluation["by_mode"]["adaptive"]
    checks = {
        "recall_at_5": adaptive["recall_at_5"] >= 0.85,
        "recall_at_10": adaptive["recall_at_10"] >= 0.95,
        "mrr": adaptive["mrr"] >= 0.80,
        "ndcg_at_10": adaptive["ndcg_at_10"] >= 0.85,
        "no_answer_f1": adaptive["no_answer_f1"] >= 0.90,
        "per_category": adaptive["per_category_minimum_recall_at_5"] >= 0.75,
        "relative_mrr": adaptive["mrr"] >= keyword["mrr"] - 0.01,
        "relative_ndcg": adaptive["ndcg_at_10"] >= keyword["ndcg_at_10"] - 0.01,
        "warm_p95": adaptive["latency_p95_ms"] <= 3500,
        "error_rate": adaptive["error_rate"] == 0,
    }
    payload = {
        "status": "PASSED" if all(checks.values()) else "FAILED", "generated_at": now_iso(),
        "split": "dev", "test_v2_labels_read": False, "checks": checks, "evaluation": evaluation,
    }
    write_json("dev_final_validation.json", payload)
    return 0 if payload["status"] == "PASSED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
