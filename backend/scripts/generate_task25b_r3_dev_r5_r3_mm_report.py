from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r3_mm"
REPORT = ROOT / "docs" / "25B_R3_DEV_R5_R3_MM_query_understanding_contract_report.md"
FINAL_STATUS = "QUERY_UNDERSTANDING_CONTRACT_NOT_READY"


def read_json(name: str) -> dict[str, Any]:
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def percent(value: float | None) -> str:
    return "NOT RUN" if value is None else f"{value * 100:.2f}%"


def milliseconds(value: float | None) -> str:
    return "NOT RUN" if value is None else f"{value:.3f} ms"


def main() -> None:
    snapshot = read_json("r5_r2_mm_snapshot.json")
    schema = read_json("schema_probe.json")
    model_ab = read_json("model_ab.json")
    context = read_json("context_merge_probe.json")
    planner = read_json("planner_probe.json")
    contract = read_json("contract_gate.json")
    canary = read_json("canary_result.json")
    vector = read_json("vector_reconciliation.json")
    regression = read_json("regression_summary.json")
    browser = read_json("browser_review.json")
    boundary = read_json("boundary_summary.json")

    models = model_ab.get("models") or {}
    m3 = models.get("MiniMax-M3") or {}
    m27 = models.get("MiniMax-M2.7-highspeed") or {}
    counts = vector.get("partition_counts") or {}
    pytest = regression.get("pytest") or {}
    security = regression.get("security") or {}
    business = regression.get("business") or {}
    frontend = regression.get("frontend") or {}
    smoke = regression.get("final_smoke") or {}

    if contract.get("status") != FINAL_STATUS or contract.get("ready") is not False:
        raise RuntimeError("Query Understanding contract evidence is not in the expected blocked state")
    if model_ab.get("selected_runtime_model") != "deterministic":
        raise RuntimeError("runtime model selection must remain deterministic when both candidates fail")
    if canary.get("executed_cases") != 0 or canary.get("formal_test_allowed") is not False:
        raise RuntimeError("Canary/formal gate boundary changed unexpectedly")
    if vector.get("read_only") is not True or vector.get("re_upserted") != 0:
        raise RuntimeError("vector reconciliation is not read-only")
    if boundary.get("backend_env_changed") is not False:
        raise RuntimeError("backend/.env boundary is not intact")
    if browser.get("status") != "PASSED" or smoke.get("status") != "PASSED":
        raise RuntimeError("browser or final smoke evidence is incomplete")

    report = f"""# Task 25B-R3-DEV-R5-R3-MM Query Understanding Contract Report

Result: `{FINAL_STATUS}`

本轮完成了 Query Understanding v2 极简合同、确定性语义合并、确定性 Retrieval Planner v2、一次性同样本 MiniMax 模型 A/B、严格前置门禁和完整回归。两个候选模型均未同时达到结构化质量与 4 秒 p95 硬门，因此生产运行时保持 `deterministic`；版本化 Canary 未运行，正式测试集未创建，RAG 最终质量未通过。本结论是门禁正确阻断，不是系统崩溃或被测试跳过。

## 1. R5-R2-MM 失败基线

- 冻结结果：`{snapshot.get('source_result')}`。
- Query Understanding：{snapshot['query_understanding']['structured_success']}/{snapshot['query_understanding']['tool_cases']} structured success，p95 {milliseconds(snapshot['query_understanding']['p95_ms'])}。
- Deterministic rerank：`{snapshot['deterministic_rerank']['status']}`，Top1 {percent(snapshot['deterministic_rerank']['top1_accuracy'])}。
- Optional Tie-break：{percent(snapshot['optional_tiebreak']['structured_success_ratio'])} structured success，p95 {milliseconds(snapshot['optional_tiebreak']['p95_ms'])}。
- R5-R2-MM 主报告及 7 份关键机器证据共 8 项 SHA-256 均未变化；旧 runtime 和失败探针未覆盖。

## 2. 复杂 Schema 失败根因

旧合同将意图分类、口语标准化、明确实体、检索假设、Anchor、通道权重和嵌套 retrieval queries 混在一次模型调用中。嵌套对象、required 字段与输出长度共同放大 `NO_TOOL_USE`、字段缺失、Schema 校验失败和重试延迟；同时职责混合使模型输出可能影响检索事实边界。修复不是增加 timeout/max_tokens，而是拆分模型与系统职责。

## 3. Query Understanding v2 Schema

- 强制工具：`submit_query_understanding_v2`；`additionalProperties=false`。
- 平面字段仅 8 个：`intent`、`canonical_query`、`requested_information`、`ambiguity`、`missing_slots`、`needs_clarification`、`clarifying_question`、`confidence`。
- `canonical_query` 最长 256；requested information 最多 3 项；missing slots 最多 4 项；追问最长 160。
- 不含 retrieval queries/hypotheses、secondary intents、device models、alarm codes、Anchor、权重或维修答案。
- 12 条真实 Schema Probe：{schema.get('passed_cases')}/{schema.get('cases')} 通过；nested retrieval query={schema.get('nested_retrieval_queries')}；唯一失败为一次 4 秒预算 timeout，状态 `{schema.get('status')}`。

## 4. 系统侧语义合并

`QueryUnderstandingMergeService` 合并确定性信号、已验证 v2 patch、会话补充与完整性判断。型号、告警、数字和条件由系统确定性结果持有；模型不能覆盖或新增型号/告警；用户补充优先于历史推测；canonical query 若违反确认实体边界会被清理并回退。

- Context Merge：{context.get('passed_cases')}/{context.get('cases')}，accuracy={percent(context.get('accuracy'))}，达到 >=95% 硬门。
- 缓存只保存 Pydantic 验证通过的 v2 patch；key 包含 provider/model/schema/prompt/query hash/confirmed signal hash/上下文澄清状态；错误与 fallback 不冒充模型成功。

## 5. 确定性 Retrieval Planner v2

- 仅由系统生成最多 4 条：ORIGINAL、CANONICAL、INTENT_QUERY、CONDITION_QUERY。
- ORIGINAL 始终保留；模型不再返回查询、Anchor 或权重。
- `COMMUNICATION` 映射 COMMUNICATION/SYMPTOM/CAUSE/ACTION/VERIFICATION；`PROCEDURE` 映射 PROCEDURE/ACTION/PREREQUISITE/SAFETY/VERIFICATION。
- 权重来自配置，检索假设标记为非事实，不使用 expected labels 或 case-id 特判。
- Planner Probe：{planner.get('passed_cases')}/{planner.get('cases')}；ORIGINAL 保留 {percent(planner.get('original_preservation_ratio'))}；最大查询数 {planner.get('max_query_count')}；型号/告警幻觉 {planner.get('hallucinated_models')}/{planner.get('hallucinated_alarms')}；状态 `{planner.get('status')}`。

## 6. M3 与 M2.7-highspeed 同样本 A/B

两个模型使用同一 30 条 Train/Dev 样本、相同 v2 Schema、Anthropic forced tool choice 和 `service_tier=standard`，每个模型只完整运行一次。

| 指标 | MiniMax-M3 | MiniMax-M2.7-highspeed | 硬门 |
|---|---:|---:|---:|
| structured success | {m3.get('structured_success')}/{m3.get('cases')} ({percent(m3.get('structured_success_ratio'))}) | {m27.get('structured_success')}/{m27.get('cases')} ({percent(m27.get('structured_success_ratio'))}) | >=95% |
| tool-use success | {percent(m3.get('tool_use_success_ratio'))} | {percent(m27.get('tool_use_success_ratio'))} | 合同必要条件 |
| intent accuracy | {percent(m3.get('intent_accuracy'))} | {percent(m27.get('intent_accuracy'))} | >=95% |
| canonicalization | {percent(m3.get('canonicalization_accuracy'))} | {percent(m27.get('canonicalization_accuracy'))} | >=90% |
| clarification precision | {percent(m3.get('clarification_precision'))} | {percent(m27.get('clarification_precision'))} | >=85% |
| clarification recall | {percent(m3.get('clarification_recall'))} | {percent(m27.get('clarification_recall'))} | >=85% |
| hallucinated model/alarm | {m3.get('hallucinated_models')}/{m3.get('hallucinated_alarms')} | {m27.get('hallucinated_models')}/{m27.get('hallucinated_alarms')} | 0/0 |
| p50 | {milliseconds((m3.get('latency_ms') or {{}}).get('p50'))} | {milliseconds((m27.get('latency_ms') or {{}}).get('p50'))} | 记录项 |
| p95 | {milliseconds((m3.get('latency_ms') or {{}}).get('p95'))} | {milliseconds((m27.get('latency_ms') or {{}}).get('p95'))} | <=4,000 ms |
| provider errors/timeouts | {m3.get('provider_errors')}/{m3.get('timeouts')} | {m27.get('provider_errors')}/{m27.get('timeouts')} | error rate=0 |
| error rate | {percent(m3.get('error_rate'))} | {percent(m27.get('error_rate'))} | 0% |
| total tokens observed | {(m3.get('token_usage') or {{}}).get('total_tokens')} | {(m27.get('token_usage') or {{}}).get('total_tokens')} | 记录项 |

M3 明确发送 thinking disabled；M2.7-highspeed 按 Provider 能力不伪造关闭。MiniMax 官方 Anthropic 文档说明 M2.x thinking 不可关闭；官方模型说明将 M2.7-highspeed 定位为相同能力的高速版本：[Anthropic API](https://platform.minimaxi.com/docs/api-reference/text-chat-anthropic)，[Models overview](https://platform.minimax.io/docs/guides/models-intro)。本轮未记录 thinking 内容、完整 prompt、完整响应或 Authorization。

## 7. 最终运行时模型选择

- 选择：`{model_ab.get('selected_runtime_model')}`。
- 原因：`{model_ab.get('selection_reason')}`。
- MiniMax-M3 未达到 structured、intent、canonicalization、clarification、零告警幻觉、p95 和 error-rate 门。
- MiniMax-M2.7-highspeed 在任务 4 秒总预算下 30/30 timeout，未达到任何模型主路径门。
- 两者均失败时按任务规定保持 deterministic normalization，未修改 `backend/.env` 的主模型配置。

## 8. 延迟、请求与重试边界

- Query Understanding 默认一次请求；普通 4xx、NO_TOOL_USE、字段缺失、未知枚举和 Schema failure 不重试。
- 仅 connection reset/refused、请求未送达、明确 502/503 可在总预算内快速重试一次。
- 总预算 4 秒，超预算立即 deterministic fallback，不允许放大到 10–20 秒。
- 探针模式完整记录错误但不因 Schema failure 开 breaker；生产 breaker 仅统计 timeout、5xx、传输错误与连续 NO_TOOL_USE；Query/Tie-break 独立。
- Schema validation failure 单独计数，M3 A/B 后 Query breaker 仍为 `{((m3.get('breaker') or {{}}).get('query_understanding') or {{}}).get('state')}`。

## 9. Tie-break

- `DeterministicEvidenceRerankService` 保持启用。
- MiniMax Tie-break 生产默认关闭，仅能通过实验/管理员显式配置开启；失败保持确定性顺序。
- Tie-break 不参与本轮 Query Understanding 前置门，也未阻断合同判定。

## 10. Contract Gate

- 状态：`{contract.get('status')}`；ready={contract.get('ready')}。
- 通过项：context merge、planner、deterministic rerank、零型号幻觉、零告警幻觉门的综合安全判断。
- 阻断项：{', '.join(contract.get('blockers') or [])}。
- 95% structured success：**未满足**。
- 4 秒 p95：**未满足**。

## 11. Canary

- 数据集名称保留为 `{canary.get('dataset')}`，但未创建/执行 60 条版本化 Canary 数据。
- 状态：`{canary.get('status')}`；executed cases={canary.get('executed_cases')}；iterations={canary.get('iterations_executed')}。
- 没有运行 iteration 2，没有执行 Train/Dev 校准，没有降低门槛。

## 12. 正式测试

- 因前置合同失败，`task25b_r3_dev_r5_r3_mm_zh_v1` 未创建、未冻结、未运行。
- 正式 run count=0；正式结果未用于调参；正式质量门未运行。

## 13. 向量只读对账

- Collection：`{vector.get('collection')}`；状态 `{vector.get('status')}`；read-only={vector.get('read_only')}。
- partition：pilot_r2={counts.get('pilot_r2')}，pilot_r3_semantic={counts.get('pilot_r3_semantic')}，pilot_r4_grounded={counts.get('pilot_r4_grounded')}，pilot_r5_query_aware={counts.get('pilot_r5_query_aware')}。
- re-embedded/re-upserted={vector.get('re_embedded')}/{vector.get('re_upserted')}。
- missing/orphan/duplicate/mismatch={vector.get('missing')}/{vector.get('orphan')}/{vector.get('duplicate')}/{vector.get('mismatch')}。
- Collection/Partition 创建删除=0；默认 Partition 修改={vector.get('default_partition_affected')}；正式全量重建未执行。

## 14. 完整回归

- compileall：`{regression.get('compileall')}`。
- Alembic heads/current：`{regression.get('alembic_heads')}` / `{regression.get('alembic_current')}`。
- pytest：{pytest.get('passed')} passed，{pytest.get('skipped')} skipped，{pytest.get('warnings')} warnings；普通 pytest 未调用真实外部 API。
- 定向 tests：unit `{regression['directed_tests']['unit']}`；integration `{regression['directed_tests']['integration']}`。
- Security：config `{security.get('config')}`；secret scan `{security.get('secret_leak_scan')}`，blocking={security.get('blocking_findings')}；log `{security.get('log_sanitization')}`；upload `{security.get('upload_security')}`。
- 上传安全在独立 PostgreSQL test schema 运行 11/11 后删除 schema 和隔离文件，生产知识文档增加 0。
- RBAC：{regression['rbac']['checks']}；业务回归：DashVector hybrid `{business.get('dashvector_hybrid_flow')}`，其余 multimodal/agents/curator/artifact/concurrency 均通过，真实 DashVector called={business.get('real_dashvector_called')}。
- 前端：npm install `{frontend.get('npm_install')}`，audit vulnerabilities={frontend.get('npm_audit_vulnerabilities')}，build `{frontend.get('build')}`，vue-tsc `{frontend.get('vue_tsc')}`，static `{frontend.get('static_install')}`。

## 15. 浏览器与 Final Smoke

- 浏览器：`{browser.get('status')}`；质量页展示 v2 11/12、M3/M2.7-HS 同样本结果、deterministic 运行时、Canary 0、Formal 未创建和向量只读不变。
- 口语通信查询实际显示“确定性标准化（无外部调用）”、4 条确定性查询和原始手册引用。
- R5-R3 面板 mutation buttons=0；RBAC 独立验证 viewer 边界；console/page/unexpected network errors=0/0/0；未渲染 Key 或 token 值。
- Final Smoke：{smoke.get('total')}/{smoke.get('total')} passed，failed={smoke.get('failed')}；默认跳过会新增 qa_records 的 retrieval write。

## 16. backend/.env 未修改

- 任务前后 SHA-256 一致：`{boundary.get('backend_env_sha256_unchanged')}`。
- 未修改 `backend/.env`，未在命令、报告、runtime、浏览器或日志输出 API Key。

## 17. 正式全量重建与审核边界

- `TASK25B_ALLOW_FULL_REINDEX=false`；正式全量重建、Embedding 再生成、真实向量 upsert 均未执行。
- engineering approval 未修改；`expert_verified=false`，未写专家审核结果。
- 未增加知识文档或 Semantic Unit；fake 业务回归产生的 3 个临时知识夹具已精确清除。

## 18. 未打包、未提交 Git

- 未创建 ZIP；任务开始时已有 {boundary.get('existing_zip_count')} 个 ZIP，hash 全部不变。
- 未执行 git add/commit/reset/clean/restore；staged count={boundary.get('git_staged_count')}；`git diff --check` 通过。
- 未执行工作区清理，用户已有脏工作区和无关改动均保留。

## Final judgment

- selected model：`deterministic`。
- why：M3 与 M2.7-highspeed 都没有满足全部模型硬门。
- same-sample result：M3={m3.get('structured_success')}/{m3.get('cases')} structured、p95 {milliseconds((m3.get('latency_ms') or {{}}).get('p95'))}；M2.7-highspeed={m27.get('structured_success')}/{m27.get('cases')} structured、p95 {milliseconds((m27.get('latency_ms') or {{}}).get('p95'))}。
- 95% structured gate：未满足。
- 4-second p95 gate：未满足。
- Canary executed：否，0 cases。
- Formal executed：否，run count 0。
- RAG final quality passed：否。
- final status：`{FINAL_STATUS}`。

## Machine evidence

本任务机器证据统一位于 `.runtime/task25b_r3_dev_r5_r3_mm/`。本轮只生成本报告，不生成其他任务 Markdown 报告。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(json.dumps({"status": "GENERATED", "result": FINAL_STATUS, "report": str(REPORT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
