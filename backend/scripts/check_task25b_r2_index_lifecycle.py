from __future__ import annotations

import argparse
import json

from task25b_r2_common import ROOT, RUNTIME, now_iso, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    collection = json.loads((RUNTIME / "pilot_collection_check.json").read_text(encoding="utf-8"))
    index = json.loads((RUNTIME / "pilot_index_result.json").read_text(encoding="utf-8"))
    ready = args.allow_real_api and collection.get("status") == "PASSED" and index.get("status") == "PASSED"
    payload = {
        "generated_at": now_iso(), "status": "READY" if ready else "BLOCKED_NO_INDEPENDENT_PILOT_INDEX",
        "test_document_prefix": "Task25BR2_Lifecycle_", "initial": "not_executed",
        "update": "not_executed", "stale_cleanup": "not_executed",
        "archived_exclusion": "not_executed", "restore": "not_executed", "idempotent": "not_executed",
        "formal_document_changed": False, "formal_review_status_changed": False,
        "blocked_reasons": [] if ready else [collection.get("status"), index.get("status")],
    }
    write_json("index_lifecycle.json", payload)
    (ROOT / "docs" / "25B_R2_index_lifecycle_report.md").write_text(
        "# Task 25B-R2 索引生命周期报告\n\n"
        f"- 状态：{payload['status']}\n"
        "- 初始/更新/归档/恢复/幂等：未执行；独立 Pilot Collection 与正式 Pilot 索引未就绪。\n"
        "- 正式文档正文、审核状态、归档状态：未修改。\n"
        "- 工程级生命周期约束由单元/集成测试覆盖，但不冒充真实 DashVector 演练。\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
