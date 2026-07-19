from __future__ import annotations

import json

from task25b_r2_common import ROOT, now_iso, write_json

from app.core.database import SessionLocal
from app.services.retrieval_pilot_service import RetrievalPilotService


def main() -> int:
    with SessionLocal() as db:
        progress = RetrievalPilotService(db).progress()
    payload = {
        "generated_at": now_iso(),
        "status": "READY_TO_FREEZE" if progress["ready_to_freeze"] else "BLOCKED_EXPERT_REVIEW",
        **progress,
        "official_dataset_frozen": False,
        "official_run_executed": False,
        "expert_boundary": "Only real authenticated expert/admin reviews count; automation wrote zero expert approvals.",
    }
    write_json("benchmark_readiness.json", payload)
    report = ROOT / "docs" / "25B_R2_expert_benchmark_review_report.md"
    report.write_text(
        "# Task 25B-R2 专家 Benchmark 审核报告\n\n"
        f"- 状态：{payload['status']}\n"
        f"- 候选总数：{payload['total']}\n"
        f"- expert_verified：{payload['expert_verified']} / 100\n"
        f"- second_reviewed：{payload['second_reviewed']} / 20\n"
        f"- vector-heavy（专家确认）：{payload['vector_heavy']} / 20\n"
        f"- no-answer（专家确认）：{payload['no_answer']} / 15\n"
        f"- 困难负样本（专家确认）：{payload['hard_negatives']} / 15\n"
        "- 自动 expert approve：0。\n"
        "- 正式数据集冻结：未执行；专家门禁未满足。\n"
        "- 正式 Pilot 盲测：未执行。\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if progress["ready_to_freeze"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
