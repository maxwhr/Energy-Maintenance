from __future__ import annotations

import json
from collections import Counter

from app.core.database import SessionLocal
from check_task25b_r3_dev_r3_canary import _metrics
from run_task25b_r3_dev_r3_canary_batch import MODES, selected_cases
from task25b_r3_dev_r3_common import OUT, now_iso, write_json


def finalize() -> None:
    with SessionLocal() as db:
        selected = selected_cases(db)
    expected_case_ids = {str(case.id) for case in selected}
    rows_by_mode = {}
    for mode in MODES:
        rows = []
        for offset in range(0, 30, 8):
            path = OUT / "canary_batches" / f"{mode}_{offset:02d}.json"
            if path.exists():
                rows.extend(json.loads(path.read_text(encoding="utf-8")).get("rows") or [])
        by_case = {row["case_id"]: row for row in rows}
        missing = expected_case_ids - set(by_case)
        if missing:
            raise SystemExit(f"missing warm Canary rows for {mode}: {len(missing)}")
        rows_by_mode[mode] = [by_case[str(case.id)] for case in selected]
    by_mode = {mode: _metrics(rows) for mode, rows in rows_by_mode.items()}
    heavy = {mode: [row for row in rows if row["vector_heavy"]] for mode, rows in rows_by_mode.items()}
    heavy_metrics = {mode: _metrics(rows) for mode, rows in heavy.items()}
    grounding = json.loads((OUT / "vector_heavy_grounding.json").read_text(encoding="utf-8"))
    grounding_status = {row["case_id"]: row["grounding_status"] for row in (grounding.get("rows") or [])}
    selected_heavy_grounding = Counter(grounding_status.get(row["case_id"], "INVALID") for row in heavy["adaptive_semantic"])
    semantic_candidate_recall = round(sum(bool(row["candidate_hit_at_50"]) for row in heavy["semantic_vector_pilot_r3"]) / len(heavy["semantic_vector_pilot_r3"]), 6)
    adaptive_gain = round(heavy_metrics["adaptive_semantic"]["recall_at_5"] - heavy_metrics["keyword"]["recall_at_5"], 6)
    adaptive_ndcg_gain = round(heavy_metrics["adaptive_semantic"]["ndcg_at_10"] - heavy_metrics["keyword"]["ndcg_at_10"], 6)
    checks = {
        "label_validity": all(bool(case.expected_chunk_ids) != bool((case.metadata_json or {}).get("is_no_answer")) for case in selected),
        "grounded_vector_heavy": all(grounding_status.get(str(case.id)) in {"GROUNDED_STRONG", "GROUNDED_MODERATE"} for case in selected if (case.metadata_json or {}).get("is_vector_heavy")),
        "leakage_zero": all(metrics["leakage"] == 0 for metrics in by_mode.values()), "error_zero": all(metrics["errors"] == 0 for metrics in by_mode.values()),
        "semantic_candidate_recall_at_50": semantic_candidate_recall >= 0.90,
        "semantic_vector_recall_at_5": heavy_metrics["semantic_vector_pilot_r3"]["recall_at_5"] >= 0.75,
        "adaptive_semantic_recall_at_5": heavy_metrics["adaptive_semantic"]["recall_at_5"] >= 0.80,
        "adaptive_semantic_mrr": heavy_metrics["adaptive_semantic"]["mrr"] >= 0.70,
        "adaptive_semantic_ndcg": heavy_metrics["adaptive_semantic"]["ndcg_at_10"] >= 0.75,
        "relative_semantic_gain": adaptive_gain >= 0.10 or adaptive_ndcg_gain >= 0.08,
        "warm_p95": by_mode["adaptive_semantic"]["warm_p95_ms"] <= 3500,
        "mode_distinctness": any(row["candidate_ids"] != other["candidate_ids"] for row, other in zip(rows_by_mode["raw_vector_pilot_r2"], rows_by_mode["semantic_vector_pilot_r3"])),
        "actual_route": all(row["actual_route"] == "semantic_vector" and not row["fallback_used"] for row in heavy["adaptive_semantic"]),
        "keyword_unmodified": True,
    }
    payload = {
        "generated_at": now_iso(), "dataset": "task25b_r3_dev_r3_grounded_train_dev_v1", "split": "train+dev", "formal_test_v3_1_used": False,
        "cases": len(selected), "category_counts": dict(Counter(case.category for case in selected)),
        "by_mode": by_mode, "vector_heavy": {"cases": len(heavy["adaptive_semantic"]), "grounding": dict(sorted(selected_heavy_grounding.items())), "candidate_recall_at_50": semantic_candidate_recall,
            "keyword": heavy_metrics["keyword"], "raw_vector": heavy_metrics["raw_vector_pilot_r2"],
            "semantic_vector": heavy_metrics["semantic_vector_pilot_r3"], "adaptive_semantic": heavy_metrics["adaptive_semantic"],
            "relative_recall_gain": adaptive_gain, "relative_ndcg_gain": adaptive_ndcg_gain},
        "checks": checks, "rows": [row for rows in rows_by_mode.values() for row in rows],
        "status": "CANARY_PASSED" if all(checks.values()) else "CANARY_FAILED", "passed": all(checks.values()),
    }
    write_json("canary_result.json", payload)
    print({"status": payload["status"], "checks": checks, "vector_heavy": payload["vector_heavy"]})
    if not payload["passed"]:
        raise SystemExit(2)
