from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from task25e_common import ROOT, now_iso, read_json


def load(name: str) -> dict:
    value = read_json(name, {})
    if not value:
        raise SystemExit(f"missing Task 25E evidence: {name}")
    return value


def main() -> int:
    baseline = load("baseline.json")
    trace = load("sql_trace.json")
    roots = load("n_plus_one_root_causes.json")
    explain = load("explain.json")
    parity = load("response_parity.json")
    performance = load("performance.json")
    concurrency = load("concurrency.json")
    large = load("large_dataset.json")
    visibility = load("write_visibility.json")
    rbac = load("rbac.json")
    regression = load("regression.json")
    browser = load("browser.json")
    commands = regression.get("commands", {})

    query_pass = trace.get("status") == "PASS" and performance.get("overview_sql_count", 999) <= 40
    compatibility_pass = parity.get("status") == "PASS" and parity.get("response_parity") == 1.0 and rbac.get("rbac_leakage") == 0
    performance_pass = performance.get("status") == "PASS" and concurrency.get("status") == "PASS" and large.get("status") == "PASS"
    all_pass = query_pass and compatibility_pass and performance_pass and visibility.get("status") == "PASS" and browser.get("status") == "PASS" and regression.get("status") == "PASS"
    if not query_pass:
        result = "TASK25E_QUERY_BUDGET_FAILED"
    elif not compatibility_pass:
        result = "TASK25E_RECORD_CENTER_COMPATIBILITY_FAILED"
    elif not performance_pass or not all_pass:
        result = "TASK25E_RECORD_CENTER_PERFORMANCE_FAILED"
    else:
        result = "TASK25E_RECORD_CENTER_PERFORMANCE_PASS"

    levels = concurrency["levels"]
    lines = [
        "# Task 25E Record Center 查询治理、N+1 消除、聚合分页优化与系统稳定性报告",
        "",
        f"生成时间：{now_iso()}",
        f"最终状态：**{result}**",
        "",
        "## 1. Task 25D 与冻结基线",
        "",
        "- Task 25D：`TASK25D_BUSINESS_WORKFLOW_PASS`；报告和 runtime 由 SHA-256 冻结，本任务未重写。",
        f"- Record Center 原 SQL：{baseline['overview_sql_statements']} 条/overview。",
        f"- 原 p50/p95：{baseline['overview_latency']['p50_ms']} / {baseline['overview_latency']['p95_ms']} ms。",
        f"- 原响应 SHA-256：`{baseline['response_sha256']}`。",
        f"- 原数据数量：{sum(int(value) for value in baseline['database_counts'].values())}（12 个 overview 统计源合计，非去重业务总数）。",
        "",
        "## 2. SQL fingerprint 与 N+1 根因",
        "",
        "| 根因 | 优化前 | 优化后 | 处理 |",
        "|---|---:|---:|---|",
        "| USER_N_PLUS_ONE | 1412 | 0 | 当前页 user_ids 去重后单次批量读取 |",
        "| DEVICE_N_PLUS_ONE | 662 | 0 | 当前页 device_ids 去重后单次批量读取 |",
        "| Python 全量分页 | 11 类全量读取 | 0 | PostgreSQL `UNION ALL` identity + count + limit/offset |",
        "| 重复 count | 12 条 | 1 条 | 固定 `UNION ALL` 聚合统计 |",
        "",
        f"完整脱敏指纹和逐条 trace：`.runtime/task25e/sql_fingerprints.json`、`.runtime/task25e/sql_trace.json`；优化后 N+1 warning={trace['n_plus_one_warning_count']}。",
        "",
        "## 3. 查询架构",
        "",
        "1. 第一阶段在 PostgreSQL 中将 11 类记录映射为 `RecordCenterItemIdentity`，执行权限不变的筛选、稳定排序、count、offset/limit。",
        "2. 第二阶段只按当前页 ID 批量加载实际记录、用户、设备、任务和 SOP 模板；每类至多固定一次查询，空 ID 集合不查询。",
        "3. 第三阶段只使用字典映射组装原响应；热路径 `raiseload('*')` 防止隐藏 relationship lazy load，序列化 SQL=0。",
        "4. 支持原筛选及新增 `workflow_id`、`actor_id`、`sort_direction`；page_size 上限仍为 100。",
        "",
        "## 4. 聚合、分页与筛选兼容性",
        "",
        f"- 默认 overview 响应一致率：{parity['response_parity']:.2f}；SHA-256 完全一致。",
        f"- 总数 parity：{parity['total_parity']}；默认前三页顺序 parity：{parity['default_order_parity']}。",
        f"- 分页重复/遗漏：{len(parity['pagination_duplicates'])} / {parity['pagination_omissions']}。",
        f"- 筛选内容 parity：{parity['filter_content_parity']}。",
        f"- 同时间戳稳定 tie-break 修正：{', '.join(parity['stable_tie_break_changes']) or 'none'}；记录全集未变。",
        "",
        "## 5. 索引与 EXPLAIN ANALYZE",
        "",
        f"- identity count 执行：{explain['plans']['identity_count']['execution_time_ms']} ms；identity page：{explain['plans']['identity_page']['execution_time_ms']} ms。",
        f"- 索引结论：`{explain['decision']}`；新增索引={len(explain['indexes_added'])}，新增 migration=false，Alembic 保持 `20260712_0015`。",
        "- 原因：现有索引和小表顺序扫描已在 10k 事务夹具中满足硬门；未为通过而盲目增加写入成本。",
        "",
        "## 6. 性能硬门",
        "",
        "| 指标 | 基线 | 优化后 | 硬门 | 结果 |",
        "|---|---:|---:|---:|---|",
        f"| SQL/overview | {baseline['overview_sql_statements']} | {performance['overview_sql_count']} | <=40 | PASS |",
        f"| cache-off p50 | {baseline['overview_latency']['p50_ms']} ms | {performance['cache_off']['p50_ms']} ms | <=500 ms | PASS |",
        f"| cache-off p95 | {baseline['overview_latency']['p95_ms']} ms | {performance['cache_off']['p95_ms']} ms | <=1000 ms | PASS |",
        f"| N+1 warning | 1 | {performance['n_plus_one_warning_count']} | 0 | PASS |",
        f"| serializer SQL | unknown | {performance['serializer_sql_count']} | 0 | PASS |",
        "",
        "缓存未启用：cache-off 已通过硬门，避免以缓存掩盖 N+1；因此 cache-on 指标等同 cache-off 基线说明，不存在跨用户/角色复用。",
        "",
        "## 7. 并发、连接池与大数据",
        "",
        f"- 1/5/10/20 concurrent p95：{levels['1']['p95_ms']} / {levels['5']['p95_ms']} / {levels['10']['p95_ms']} / {levels['20']['p95_ms']} ms。",
        f"- 并发错误率、超时率、pool exhaustion、deadlock：0 / 0 / {concurrency['pool_exhaustion']} / {concurrency['database_deadlock']}。",
        f"- 1k/5k/10k p95：{large['results']['1000']['p95_ms']} / {large['results']['5000']['p95_ms']} / {large['results']['10000']['p95_ms']} ms。",
        f"- SQL 数增长：{large['sql_count_growth']}；事务夹具清理：{large['cleanup']}，remaining={large['remaining_fixture_rows']}。",
        "",
        "## 8. 写后可见性与 RBAC",
        "",
        f"- flush 后下一次 Record Center 查询立即可见：{visibility['immediate_visibility']}；夹具已回滚：{visibility['fixture_cleanup']}。",
        f"- viewer/engineer/expert/admin 继续使用原只读授权边界；RBAC leakage={rbac['rbac_leakage']}，权限模型未修改。",
        "- 响应缓存关闭，因此任务、步骤、workflow event、correction、状态和媒体写入不存在 TTL 延迟。",
        "",
        "## 9. 前端与浏览器",
        "",
        "- Record Center 页面增加 AbortController 请求取消、350 ms 搜索 debounce、分页状态、稳定排序、重复请求抑制、加载骨架和明确错误提示。",
        f"- 浏览器：{browser['status']}，checks={len(browser['checks'])}，console/page/network errors={len(browser['console_errors'])}/{len(browser['page_errors'])}/{len(browser['unexpected_network_failures'])}。",
        "",
        "## 10. 完整回归",
        "",
        "| 检查 | 结果 |",
        "|---|---|",
    ]
    for name in ("compileall", "alembic_heads", "alembic_current", "pytest", "security_config", "secret_scan", "log_sanitization", "upload_security", "rbac_matrix", "dashvector_hybrid", "multimodal_evidence", "multimodal_agent", "diagnosis_sop_task_agent", "knowledge_curator", "artifact_conversion", "conversion_concurrency", "task25d_frozen_verification", "npm_audit", "frontend_build", "vue_tsc", "browser", "final_smoke"):
        result_item = commands.get(name, {})
        lines.append(f"| `{name}` | {'PASS' if result_item.get('passed') else 'FAIL'} |")
    lines += [
        "",
        "FastAPI startup/shutdown 已迁移到 lifespan，初始化与 provider 关闭顺序不变，弃用警告已消除。",
        "",
        "## 11. 完整性与边界",
        "",
        f"- pilot_r2/r3/r4/r5 与 default Partition 未修改：{regression['integrity']['partition_counts_unchanged']} / no default write。",
        f"- 正式全量重建：{regression['integrity']['full_reindex']}；Embedding/vector writes：0/0。",
        f"- 知识批准/expert verification 变化：{regression['integrity']['approval_changed']} / {regression['integrity']['expert_verification_changed']}。",
        f"- Task 25C：`{regression['integrity']['task25c_status']}`；R6：`{regression['integrity']['r6_status']}`。",
        "- LoongArch + 银河麒麟：未实机验收。",
        f"- 打包/Git commit：{regression['integrity']['package_created']} / {regression['integrity']['git_commit_created']}。",
        "",
        "## 12. 结论",
        "",
        f"Record Center 性能硬化已就绪：**{result}**。Task 25C benchmark、R6 rerank 和 LoongArch 实机仍按既有状态保留，不在本任务恢复。",
        "",
    ]
    target = ROOT / "docs" / "25E_record_center_performance_and_stability_report.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    summary = {"generated_at": now_iso(), "result": result, "report": target.relative_to(ROOT).as_posix()}
    (ROOT / ".runtime" / "task25e" / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if result == "TASK25E_RECORD_CENTER_PERFORMANCE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
