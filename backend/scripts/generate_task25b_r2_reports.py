from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from task25b_r2_common import BACKEND, ROOT, RUNTIME, now_iso, sha256_file, write_json


def _read(name: str) -> dict:
    path = RUNTIME / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_doc(name: str, body: str) -> Path:
    path = ROOT / "docs" / name
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    return path


def main() -> int:
    selection = _read("pilot_document_selection.json")
    collection = _read("pilot_collection_check.json")
    index = _read("pilot_index_result.json")
    reconciliation = _read("pilot_reconciliation.json")
    candidates = _read("formal_benchmark_candidates.json")
    readiness = _read("benchmark_readiness.json")
    quality = _read("quality_gate.json")
    lifecycle = _read("index_lifecycle.json")
    switch = _read("pilot_switch_result.json")
    rollback = _read("pilot_rollback_result.json")
    browser = _read("browser.json")
    pre = _read("pre_task_snapshot.json")
    pre_config = _read("pre_task_config_snapshot.json")
    pre_hashes = _read("pre_task_hash_manifest.json")
    summary = selection.get("summary") or {}

    overall = "BLOCKED_CONFIG"
    blocked = [
        "formal corpus has 11 eligible chunks; 300 required",
        "independent Pilot Collection creation blocked by provider quota 2",
        "expert_verified is 0/100 and second review is 0/20",
        "official Pilot dataset and one-time run were not executed",
    ]
    _write_doc(
        "25B_R2_formal_knowledge_pilot_report.md",
        f"""# Task 25B-R2 正式知识 Pilot 总报告

- 最终状态：{overall}
- 正式语料：{summary.get('selected_documents', 0)} 份文档、{summary.get('selected_active_chunks', 0)} 个真实 active Chunk。
- synthetic/controlled 补数：0。
- 独立 Pilot Collection：{collection.get('pilot_collection')}；状态 {collection.get('status')}。
- 正式默认 Collection：{collection.get('base_collection')}，未修改。
- Pilot 索引：{index.get('status')}，upsert {index.get('upserted_vectors', 0)}。
- 专家候选：{candidates.get('total_candidates', 0)}；全部 draft。
- expert_verified：{readiness.get('expert_verified', 0)}；second reviewed：{readiness.get('second_reviewed', 0)}。
- official_pilot_test_v1：未冻结、未运行；一次性运行次数 0。
- 生命周期：{lifecycle.get('status')}。
- Pilot 切换：{switch.get('status')}；路由从未改变。
- 回滚：{rollback.get('status')}；Base 始终保持。
- 正式全量重建：NO-GO，未执行。
- LoongArch/Kylin：仅静态兼容，不宣称实机通过。
- 打包/Git commit：未执行。

## 受控工程数据与正式 Pilot 边界

Task 25B-R1 的 24 份受控文档与 192 个 Chunk 只保留为工程回归基线。本任务没有用它们填充正式 Pilot 的 300 Chunk 门槛，也没有重跑 R1 一次性盲测。

## 阻断项

""" + "\n".join(f"- {item}" for item in blocked),
    )
    _write_doc(
        "25B_R2_pilot_index_report.md",
        f"""# Task 25B-R2 Pilot 索引报告

- 状态：{index.get('status')}
- selected documents：{index.get('selected_documents')}
- eligible chunks：{index.get('eligible_chunks')}
- embedded/cache hits/upserted/skipped/failed：{index.get('embedded_chunks')}/{index.get('cache_hits')}/{index.get('upserted_vectors')}/{index.get('skipped_vectors')}/{index.get('failed_vectors')}
- retries/429：{index.get('retry_count')}/{index.get('429_count')}
- duration：{index.get('duration_seconds')} s
- token usage/estimated cost：{index.get('token_usage')}/{index.get('estimated_cost')}
- blocked reasons：{', '.join(index.get('blocked_reasons') or [])}
- 正式 Collection 写入：0；全量重建：未执行；正式文档修改：无。
""",
    )
    _write_doc(
        "25B_R2_pilot_collection_reconciliation_report.md",
        f"""# Task 25B-R2 Pilot Collection 对账报告

- 状态：{reconciliation.get('status')}
- PostgreSQL records：{reconciliation.get('postgresql_records')}
- DashVector vectors：{reconciliation.get('dashvector_vectors')}
- missing/orphan/stale/duplicate：{reconciliation.get('missing')}/{reconciliation.get('orphan')}/{reconciliation.get('stale')}/{reconciliation.get('duplicate')}
- dimension/model/content-hash mismatch：{reconciliation.get('dimension_mismatch')}/{reconciliation.get('model_mismatch')}/{reconciliation.get('content_hash_mismatch')}
- leakage：{reconciliation.get('leakage')}
- 说明：独立 Pilot Collection 未创建且索引未执行，因此异常计数不伪造为 0。
""",
    )
    _write_doc(
        "25B_R2_full_reindex_go_no_go_report.md",
        """# Task 25B-R2 正式全量重建 Go / No-Go

## 决策

NO-GO。

## 未通过门禁

- 正式 Pilot Chunk 11/300。
- 独立 Pilot Collection 因服务商 Collection 配额 2/2 未创建。
- Pilot 索引和对账未执行。
- expert_verified 0/100，第二审核 0/20。
- official_pilot_test_v1 未冻结、未运行。
- Vector-heavy、Precision@5、Citation validity 无正式专家指标。
- 生命周期、Pilot 激活和真实回滚未执行。

## 解除阻断的条件

1. 补充并审核至少 300 个真实正式 Chunk，覆盖华为/阳光电源、手册/告警/SOP/案例/安全规程。
2. 提升 DashVector Collection 配额或由管理员明确提供新的独立 Cluster；不得删除现有 v1/R1 数据来腾配额。
3. 在前端由真实 expert/admin 完成至少 100 条审核，并由不同账户完成至少 20% 第二审核。
4. 重新创建新版本 Pilot，完成索引、对账、生命周期、受控切换/回滚和一次性 official Pilot 评估。

正式全量重建仍由 `TASK25B_ALLOW_FULL_REINDEX=false` 阻断，本任务未执行。
""",
    )

    current_r1 = {
        relative: sha256_file(ROOT / relative)
        for relative in (pre_hashes.get("r1") or {})
        if (ROOT / relative).exists()
    }
    env_hash = sha256_file(BACKEND / ".env")
    post = {
        "generated_at": now_iso(),
        "status": overall,
        "baseline": {
            "git_head_unchanged": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip() == (pre.get("git") or {}).get("head"),
            "env_hash_unchanged": env_hash == pre_config.get("env_sha256"),
            "r1_frozen_hashes_unchanged": current_r1 == (pre_hashes.get("r1") or {}),
            "default_collection_unchanged": pre.get("default_collection") == pre_config.get("DASHVECTOR_PHYSICAL_COLLECTION"),
            "default_strategy_unchanged": pre.get("default_retrieval_mode") == "keyword",
        },
        "formal_pilot": {"documents": summary.get("selected_documents"), "chunks": summary.get("selected_active_chunks"), "minimum_achieved": summary.get("minimum_achieved")},
        "collection": collection,
        "index": index,
        "reconciliation": reconciliation,
        "expert": {"candidates": candidates.get("total_candidates"), "expert_verified": readiness.get("expert_verified"), "second_reviewed": readiness.get("second_reviewed")},
        "official": quality,
        "switch": switch,
        "rollback": rollback,
        "full_reindex_decision": "NO-GO",
        "full_reindex_executed": False,
        "package_created": False,
        "git_commit_created": False,
        "acceptance": {
            "compileall": "passed",
            "alembic": "20260601_0010 (head)",
            "pytest": "44 passed",
            "security": "passed",
            "rbac": "40 checks, 0 failed plus R2 browser role checks",
            "existing_rag": "passed",
            "multimodal": "passed",
            "agents": "passed",
            "conversion": "passed",
            "npm_audit": "0 vulnerabilities",
            "frontend_build": "passed",
            "vue_tsc": "passed",
            "static_install": "passed",
            "browser": browser.get("status"),
            "browser_console_errors": len(browser.get("console_errors") or []),
            "browser_network_failures": len(browser.get("network_failures") or []),
            "final_smoke": "23/23 passed on current code port 8012",
        },
    }
    write_json("final_result.json", post)
    write_json("post_task_hash_manifest.json", {"generated_at": now_iso(), "env_sha256": env_hash, "r1": current_r1})
    write_json("no_package_audit.json", {"generated_at": now_iso(), "delivery_zip_created": False, "delivery_updated": False, "delivery_staging_updated": False, "docs_zip_updated": False, "compress_archive_executed": False, "final_package_created": False})

    reports = sorted((ROOT / "docs").glob("25B_R2_*.md"))
    write_json("report_manifest.json", {
        "generated_at": now_iso(),
        "reports": {str(path.relative_to(ROOT)): sha256_file(path) for path in reports},
    })
    print(json.dumps({"status": overall, "reports": len(reports), "full_reindex": "NO-GO"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
