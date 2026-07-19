from __future__ import annotations

import argparse
import json

from task25b_r2_common import ROOT, now_iso, write_json

from app.core.database import SessionLocal
from app.services.retrieval_pilot_service import RetrievalPilotService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    parser.add_argument("--official-pilot-test", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        progress = RetrievalPilotService(db).progress()
        freezes = RetrievalPilotService(db).list_freezes()
    blocked = not progress["ready_to_freeze"]
    payload = {
        "generated_at": now_iso(),
        "status": "NOT_EXECUTED_BLOCKED_EXPERT_REVIEW" if blocked else "READY_NOT_EXECUTED",
        "official_flag_requested": args.official_pilot_test,
        "dataset_version": "official_pilot_test_v1",
        "dataset_frozen": any(item["dataset_version"] == "official_pilot_test_v1" and item["freeze_status"] == "frozen" for item in freezes),
        "case_count": progress["expert_verified"], "expert_verified": progress["expert_verified"],
        "official_runs": 0, "duplicate_run_blocked": None, "label_leakage": False,
        "metrics": None, "quality_gate": "NOT_EXECUTED",
        "failed_requirements": progress["failed_requirements"],
        "external_api_called": False, "formal_run_lock_acquired": False,
    }
    write_json("official_pilot_dataset.json", {
        "version": "official_pilot_test_v1", "frozen": payload["dataset_frozen"],
        "case_count": progress["expert_verified"], "sha256": None, "reviewers": [],
    })
    write_json("official_pilot_evaluation.json", payload)
    write_json("quality_gate.json", payload)
    (ROOT / "docs" / "25B_R2_official_pilot_evaluation_report.md").write_text(
        "# Task 25B-R2 正式 Pilot 评估报告\n\n"
        f"- 状态：{payload['status']}\n- 数据集冻结：{payload['dataset_frozen']}\n"
        f"- expert_verified：{payload['expert_verified']} / 100\n- 正式运行次数：0\n"
        "- keyword/vector/hybrid/adaptive 指标：未执行。\n"
        "- 原因：专家门禁与正式语料/Pilot Collection 前置门禁未满足。\n"
        "- 一次性正式运行未被消耗。\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
