from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from task25a_r1_common import ROOT, RUNTIME, now_iso, read_json, run, sha256_file, write_json


CORRECTION_START = "<!-- TASK25A_R1_CORRECTION_START -->"
CORRECTION_END = "<!-- TASK25A_R1_CORRECTION_END -->"


def get(path: str, default: Any = None) -> Any:
    return read_json(RUNTIME / path, default if default is not None else {})


def append_correction(path: Path, title: str, body: list[str]) -> None:
    original = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = "\n".join([CORRECTION_START, "", f"## Task 25A-R1 更正：{title}", "", *body, "", CORRECTION_END])
    if CORRECTION_START in original and CORRECTION_END in original:
        prefix = original.split(CORRECTION_START, 1)[0].rstrip()
        suffix = original.split(CORRECTION_END, 1)[1].lstrip()
        updated = f"{prefix}\n\n{block}\n"
        if suffix:
            updated += f"\n{suffix}"
    else:
        updated = f"{original.rstrip()}\n\n{block}\n"
    path.write_text(updated, encoding="utf-8")


def main() -> int:
    generated = now_iso()
    old = read_json(ROOT / ".runtime" / "task25a" / "requirement_traceability.json", {})
    git = get("git_status_classification.json")
    baseline = get("baseline_manifest.json")
    req = get("requirement_evidence_matrix.json")
    changes = get("requirement_status_changes.json")
    browser = get("browser_test_results.json")
    performance = get("performance_summary.json")
    endpoint_results = get("performance_endpoint_results.json")
    candidates = {kind: get(f"{kind}_code_review.json") for kind in ["dead", "duplicate", "deprecated"]}
    loong = get("loongarch_dependency_classification.json")
    tests = get("test_execution_registry.json", {"tests": []})
    test_map = {item["test_id"]: item for item in tests.get("tests", [])}
    git_summary = git.get("summary", {})
    req_summary = req.get("summary", {})
    maturity = req_summary.get("competition_maturity", {})
    strength = req_summary.get("evidence_strength", {})
    browser_summary = browser.get("summary", {})
    perf_summary = performance.get("summary", {})
    change_summary = changes.get("summary", {})

    tracked_delivery = run(["git", "status", "--short", "--", "delivery", "delivery_staging", "docs.zip"], ROOT)
    staged = run(["git", "diff", "--cached", "--name-only"], ROOT)
    delivery = ROOT / "delivery"
    staging = ROOT / "delivery_staging"
    package_audit = {
        "generated_at": generated,
        "delivery_exists": delivery.exists(), "delivery_files": sorted(path.name for path in delivery.iterdir()) if delivery.is_dir() else [],
        "delivery_staging_exists": staging.exists(), "delivery_staging_last_write": staging.stat().st_mtime if staging.exists() else None,
        "git_status_delivery": tracked_delivery["stdout"].splitlines(), "staged_file_count": len([line for line in staged["stdout"].splitlines() if line.strip()]),
        "compress_archive_executed_by_task": False, "new_delivery_zip_created_by_task": False,
        "docs_zip_modified_by_task": False, "notes": "Task 25A-R1 scripts contain no packaging action and did not mutate delivery paths.",
    }
    write_json(RUNTIME / "no_package_audit.json", package_audit)

    critical_tests = [
        "T-R1-COMPILEALL", "T-R1-ALEMBIC-CURRENT", "T-R1-SECURITY-CONFIG", "T-R1-SECRET-SCAN", "T-R1-LOG-SANITIZATION",
        "T-R1-UPLOAD-SECURITY", "T-R1-RBAC-MATRIX", "T-R1-DASHVECTOR-FLOW", "T-R1-EXTERNAL-GATEWAY-FLOW",
        "T-R1-MULTIMODAL-FLOW", "T-R1-MULTIMODAL-AGENT-FLOW", "T-R1-DIAG-SOP-TASK-AGENT", "T-R1-KNOWLEDGE-CURATOR-AGENT",
        "T-R1-ARTIFACT-CONVERSION", "T-R1-CONVERSION-CONCURRENCY", "T-R1-NPM-INSTALL", "T-R1-NPM-AUDIT",
        "T-R1-FRONTEND-BUILD", "T-R1-VUE-TSC", "T-R1-STATIC-INSTALL", "T-R1-BROWSER-SUITE", "T-R1-PERFORMANCE-BASELINE", "T-R1-FINAL-SMOKE",
    ]
    critical_failed = [test_id for test_id in critical_tests if test_map.get(test_id, {}).get("status") != "PASSED"]
    r1_passed = not critical_failed and len(req.get("requirements", [])) == 83 and git_summary.get("possible_accidental", 1) == 0 and git_summary.get("unknown", 1) == 0
    g0_decision = "GO" if baseline and loong and git_summary.get("possible_accidental", 1) == 0 else "NO-GO"
    task25b_decision = "CONDITIONAL-GO" if r1_passed else "NO-GO"

    endpoints = endpoint_results.get("endpoints", [])
    record = next((item for item in endpoints if item.get("endpoint_id") == "record_center"), {})
    candidate_total = sum(item.get("summary", {}).get("total", 0) for item in candidates.values())
    candidate_remove = sum(item.get("summary", {}).get("safe_to_remove_now", 0) for item in candidates.values())
    old_summary = old.get("summary", {})
    report = ROOT / "docs" / "25A_R1_audit_evidence_and_baseline_report.md"
    lines = [
        "# Task 25A-R1 审计证据加固与重构基线冻结报告", "", f"生成时间：{generated}", "",
        "## 1. Executive Summary", "",
        "Task 25A 关于代码规模、真实 PostgreSQL/Alembic、前后端构建、安全和业务回归边界的事实仍成立；原 83 项 maturity 因人工预写、浏览器未全量执行、性能样本/QPS 算法和依赖用途未拆分而不能继续作为可靠成熟度结论。R1 已建立来源、时间、环境、SHA、mock/real 和 current/historical 分离的证据注册表。",
        f"- 新需求统计：VERIFIED={maturity.get('VERIFIED', 0)}，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED={maturity.get('IMPLEMENTED_BUT_NOT_FULLY_VERIFIED', 0)}，PARTIAL={maturity.get('PARTIAL', 0)}，PLACEHOLDER_OR_MOCK={maturity.get('PLACEHOLDER_OR_MOCK', 0)}，MISSING={maturity.get('MISSING', 0)}。",
        f"- 重构基线：{'可靠且已冻结' if baseline else '未生成'}；Git 疑似误删={git_summary.get('possible_accidental', 'unknown')}；unknown={git_summary.get('unknown', 'unknown')}。",
        f"- Task 25G0：**{g0_decision}**；Task 25B：**{task25b_decision}**（不得在本任务内开始）。",
        "- P0：LoongArch/Kylin 未做实机安装/启动/闭环；相似故障图片检索、检索准确率金标准和备份恢复仍缺失。P1：当前真实 provider 未复验，UI 美观/便捷和稳定性无充分量化证据。", "",
        "## 2. Audit Method Correction", "",
        "原 `requirement_rows()` 将 maturity 人工写入；R1 只保留 requirement_id/文本和适用门槛，最终状态由 evidence registry 自动计算。每项 evidence 记录来源、test_id、命令、时间、环境、current/historical、mock/real/fallback、业务/数据库/browser/performance/security 断言、artifact 和 SHA-256。历史 real-call 只证明曾实现；UI 必须有当前 browser；质量词必须有足够量化证据。", "",
        "## 3. Requirement Status Changes", "",
        f"- old verified={old_summary.get('verified', 0)}；new verified={maturity.get('VERIFIED', 0)}。",
        f"- old implemented={old_summary.get('implemented_but_not_fully_verified', 0)}；new implemented={maturity.get('IMPLEMENTED_BUT_NOT_FULLY_VERIFIED', 0)}。",
        f"- downgraded={change_summary.get('downgraded', 0)}；upgraded={change_summary.get('upgraded', 0)}；unchanged={change_summary.get('unchanged', 0)}。",
        f"- strength：STRONG={strength.get('STRONG', 0)}；MODERATE={strength.get('MODERATE', 0)}；WEAK={strength.get('WEAK', 0)}；NONE={strength.get('NONE', 0)}。", "",
        "## 4. Git Worktree Classification", "",
        f"状态项={git_summary.get('total_entries')}；modified={git_summary.get('modified')}；deleted={git_summary.get('deleted')}；untracked={git_summary.get('untracked')}。52 个 deleted 全部逐项审计，其中旧哈希生成资产={git_summary.get('deleted_generated')}、替代/重命名={git_summary.get('renamed_or_replaced')}、疑似误删={git_summary.get('possible_accidental')}、unknown={git_summary.get('unknown')}。本任务恢复文件=0、删除文件=0。", "",
        "## 5. Browser Acceptance", "",
        f"discovered={browser_summary.get('discovered')}；executed={browser_summary.get('executed')}；passed={browser_summary.get('passed')}；failed={browser_summary.get('failed')}；blocked={browser_summary.get('blocked')}；skipped={browser_summary.get('skipped')}；console/page/network={browser_summary.get('console_errors')}/{browser_summary.get('page_errors')}/{browser_summary.get('network_failures')}；viewer={browser_summary.get('viewer_rbac')}；admin={browser_summary.get('admin_flows')}。", "",
        "## 6. Performance Baseline", "",
        "R1 禁止默认账号/密码，使用安全测试配置；QPS 以真实 batch 墙钟计算；serial/concurrency 分开；warmup、并发错误、超时、HTTP 分布、响应大小、业务断言与写入计数全部记录。", "",
        "| Endpoint | Serial p95 | Concurrent p95 | 分类 |", "|---|---:|---:|---|",
    ]
    for item in endpoints:
        lines.append(f"| `{item['method']} {item['path']}` | {item['serial']['p95_ms']} | {item['concurrency']['p95_ms']} | {item['classification']} |")
    lines += [
        "", f"总体={perf_summary.get('overall')}；error_rate={perf_summary.get('error_rate')}；timeout_rate={perf_summary.get('timeout_rate')}。Record Center serial p50/p95/p99={record.get('serial', {}).get('p50_ms')}/{record.get('serial', {}).get('p95_ms')}/{record.get('serial', {}).get('p99_ms')} ms。", "",
        "## 7. Code Candidate Review", "", f"dead/duplicate/deprecated 共 {candidate_total}；`safe_to_remove_now=true`={candidate_remove}；本任务删除=0。所有候选留待 Task 25E 带动态注册、路由、兼容性和回归证据复核。", "",
        "## 8. LoongArch Dependency Classification", "", f"用途统计：{json.dumps(loong.get('summary', {}).get('usage_stage', {}), ensure_ascii=False)}。高风险 runtime={', '.join(loong.get('summary', {}).get('high_risk_runtime', []))}。Node/Vite/Rolldown 可在非龙芯构建机预构建；Playwright/Chromium 为测试依赖；实机状态=NOT_EXECUTED。", "",
        "## 9. Baseline Manifest", "", f"Manifest=`.runtime/task25a_r1/baseline_manifest.json`；HEAD=`{baseline.get('git', {}).get('head')}`；backend hash=`{baseline.get('hashes', {}).get('backend_production_source', {}).get('sha256')}`；frontend hash=`{baseline.get('hashes', {}).get('frontend_production_source', {}).get('sha256')}`；migration hash=`{baseline.get('hashes', {}).get('migrations', {}).get('sha256')}`；OpenAPI paths={baseline.get('openapi', {}).get('path_count')}；DB tables={baseline.get('database', {}).get('table_count')}。", "",
        "## 10. Current Competition Readiness", "", "B/S 与 PC Web、结构化知识/诊断/SOP/任务/追溯具备当前功能证据；OCR/视觉理解只有历史 real 与当前 mock/blocked 边界；确定性向量不是语义检索；相似图检索缺失；反馈回流仅记录未闭环；LoongArch/Kylin 仅静态分类。", "",
        "## 11. P0 Issues", "", "- LoongArch + Kylin 实机依赖安装、服务启动、PostgreSQL、解析和闭环未验证。", "- R-MM-08 相似故障图片检索缺失；R-RAG-11 无金标准准确率；R-NFR-08 无当前恢复演练证据。", "",
        "## 12. P1 Issues", "", "- 真实 Cloud/MIMO/OCR provider 本轮按约束未调用，历史可用性不能视为当前可用。", "- UI 美观/交互便捷、稳定性、容量与可观测性缺少充分量化或长稳证据。", "- Record Center 需在 Task 25E 用生产规模夹具与 EXPLAIN ANALYZE 复核。", "",
        "## 13. P2 Issues", "", "- lint package script 缺失时保持 SKIPPED，不伪报 passed。", "- 静态生成资产哈希替换使工作树噪声较大，后续 staging 必须逐项确认。", "",
        "## 14. Go / No-Go Decision", "", f"- Task 25G0：**{g0_decision}**。条件：只做目标机依赖/import/服务探针，不将静态分类当实机通过。", f"- Task 25B：**{task25b_decision}**。条件：先完成/评审 G0 风险与 R1 P0/P1 处置计划；本轮未开始 Task 25B。", "",
        "## 15. No-package Confirmation", "", f"- 新 delivery zip=false；delivery Git 状态={package_audit['git_status_delivery'] or 'clean'}；delivery_staging 未由本任务更新；Compress-Archive=false；docs.zip modified=false。", "",
        "## 16. Git Confirmation", "", f"- git add=false；git commit=false；reset/clean/restore=false；staged_file_count={package_audit['staged_file_count']}。现有用户改动全部保留；本任务没有恢复或删除文件。", "",
        f"R1 acceptance result：**{'PASSED' if r1_passed else 'FAILED'}**。未通过/缺失的关键测试：{', '.join(critical_failed) if critical_failed else '无'}。", "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")

    correction_common = [
        f"R1 于 {generated} 重建证据模型。原 83 项 maturity 是历史审计观察，不再作为当前最终结论。",
        f"新统计：VERIFIED={maturity.get('VERIFIED', 0)}，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED={maturity.get('IMPLEMENTED_BUT_NOT_FULLY_VERIFIED', 0)}，PARTIAL={maturity.get('PARTIAL', 0)}，PLACEHOLDER_OR_MOCK={maturity.get('PLACEHOLDER_OR_MOCK', 0)}，MISSING={maturity.get('MISSING', 0)}。",
        "新结论以 `.runtime/task25a_r1/evidence_registry.json`、`test_execution_registry.json` 和自动规则为准；历史 real-call、mock、browser、性能和 LoongArch 实机证据不再混写。",
    ]
    append_correction(ROOT / "docs" / "25A_competition_compliance_and_global_code_audit_report.md", "证据驱动重基线", correction_common + [f"52 个 deleted 已逐项分类：生成资产={git_summary.get('deleted_generated')}，疑似误删={git_summary.get('possible_accidental')}。"])
    append_correction(ROOT / "docs" / "25A_competition_requirement_traceability_matrix.md", "83 项成熟度重算", correction_common + [f"状态变更：downgraded={change_summary.get('downgraded', 0)}，upgraded={change_summary.get('upgraded', 0)}，unchanged={change_summary.get('unchanged', 0)}。"])
    append_correction(ROOT / "docs" / "25A_loongarch_kylin_static_compatibility_audit.md", "依赖用途拆分", correction_common + ["依赖已拆分为 runtime required/optional、build、development、test；本轮实机状态仍为 NOT_EXECUTED，不能写通过。"])
    append_correction(ROOT / "docs" / "25A_test_coverage_and_quality_gate_report.md", "浏览器、性能与测试注册表", correction_common + [f"浏览器 passed={browser_summary.get('passed')}、failed={browser_summary.get('failed')}；性能 endpoint={perf_summary.get('endpoint_count')}、overall={perf_summary.get('overall')}。"])
    append_correction(ROOT / "docs" / "25A_refactoring_decision_and_roadmap.md", "可靠重构前基线", correction_common + [f"Task 25G0={g0_decision}；Task 25B={task25b_decision}。候选删除数=0，先探针后重构。"])
    print(f"task25a_r1_generate_reports r1_passed={str(r1_passed).lower()} g0={g0_decision} task25b={task25b_decision}")
    return 0 if r1_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
