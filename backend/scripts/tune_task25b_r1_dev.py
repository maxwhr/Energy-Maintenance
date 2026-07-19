from __future__ import annotations

import argparse
import itertools
import statistics
from collections import defaultdict

from task25b_r1_common import now_iso, write_json
from task25b_r1_eval_common import evaluate_split
from app.services.retrieval_evaluation_service import RetrievalEvaluationService


def _offline_search(rows: list[dict]) -> dict:
    grouped: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        grouped[row["case_id"]][row["mode"]] = row
    results = []
    for keyword_weight, rrf_k in itertools.product((0.60, 0.70, 0.80, 0.90), (20, 40, 60)):
        vector_weight = 1.0 - keyword_weight
        metrics = []
        for modes in grouped.values():
            base = modes.get("keyword")
            vector = modes.get("vector")
            if not base or not vector or base["category"] == "no_answer":
                continue
            keyword_ids = base["keyword_candidates"]
            vector_ids = vector["vector_candidates"]
            scores = defaultdict(float)
            for rank, item in enumerate(keyword_ids, 1):
                scores[item] += keyword_weight / (rrf_k + rank)
            for rank, item in enumerate(vector_ids, 1):
                scores[item] += vector_weight / (rrf_k + rank)
            ranked = [item for item, _ in sorted(scores.items(), key=lambda pair: (pair[1], pair[0]), reverse=True)[:10]]
            metrics.append(RetrievalEvaluationService.compute_metrics(ranked, base["expected_ids"]))
        results.append({
            "keyword_weight": keyword_weight, "vector_weight": vector_weight, "rrf_k": rrf_k,
            "mrr": statistics.fmean(item["mrr"] for item in metrics),
            "ndcg_at_10": statistics.fmean(item["ndcg_at_10"] for item in metrics),
            "recall_at_10": statistics.fmean(item["recall_at_10"] for item in metrics),
        })
    results.sort(key=lambda item: (item["ndcg_at_10"], item["mrr"], item["recall_at_10"], item["keyword_weight"]), reverse=True)
    return {"search_space": results, "selected": results[0]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise RuntimeError("--allow-real-api is required")
    evaluation = evaluate_split(
        split="dev", modes=["keyword", "vector", "hybrid", "hybrid_rerank", "adaptive"], allow_blind=False
    )
    search = _offline_search(evaluation["rows"])
    by_mode = evaluation["by_mode"]
    hybrid = by_mode["hybrid"]
    rerank = by_mode["hybrid_rerank"]
    rerank_gain = rerank["ndcg_at_10"] - hybrid["ndcg_at_10"]
    reranker_enabled = rerank_gain > 0.001 and rerank["mrr"] >= hybrid["mrr"] - 0.01
    payload = {
        "status": "PASSED", "generated_at": now_iso(), "tuning_splits": ["train", "dev"],
        "test_v2_labels_read": False, "test_v2_tuning_allowed": False,
        "evaluation": evaluation, "parameter_search": search,
        "selected_parameters": {
            **search["selected"], "vector_similarity_threshold": 0.76,
            "reranker_enabled": reranker_enabled,
            "reranker_disabled_reason": None if reranker_enabled else "no_measurable_dev_gain",
        },
        "reranker_dev_ndcg_gain": round(rerank_gain, 6),
    }
    write_json("dev_tuning.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
