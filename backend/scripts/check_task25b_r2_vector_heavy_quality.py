from __future__ import annotations

import argparse
import json

from task25b_r2_common import ROOT, now_iso, write_json

from app.core.database import SessionLocal
from app.services.retrieval_pilot_service import RetrievalPilotService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        progress = RetrievalPilotService(db).progress()
    cases = int(progress.get("vector_heavy") or 0)
    payload = {
        "generated_at": now_iso(), "status": "BLOCKED_EXPERT_REVIEW" if cases < 20 else "READY",
        "expert_verified_vector_heavy_cases": cases, "required_cases": 20,
        "keyword_recall_at_5": None, "vector_recall_at_5": None, "adaptive_recall_at_5": None,
        "adaptive_mrr": None, "adaptive_ndcg_at_10": None, "improvement": None,
        "gate": "NOT_EXECUTED" if cases < 20 else "PENDING_OFFICIAL_RUN",
        "external_api_called": False, "official_labels_read": False,
    }
    write_json("vector_heavy_quality.json", payload)
    (ROOT / "docs" / "25B_R2_vector_heavy_evaluation_report.md").write_text(
        "# Task 25B-R2 Vector-Heavy 专项报告\n\n"
        f"- 状态：{payload['status']}\n- expert_verified vector-heavy：{cases} / 20\n"
        "- 指标：未执行；不得用 draft 候选替代专家审核样本。\n"
        "- 结论：不能宣称语义向量相对 keyword 有正式泛化增益。\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if cases >= 20 else 2


if __name__ == "__main__":
    raise SystemExit(main())
