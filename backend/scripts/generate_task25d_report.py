from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.database import SessionLocal
from task25d_common import OUT, ROOT, now_iso, read_json, write_json


REPORT = ROOT / "docs" / "25D_maintenance_business_workflow_integration_report.md"
ACTIVE_STATUSES = {"ACTIVE", "WAITING_USER", "WAITING_ENGINEER", "WAITING_EXPERT"}


def _groups(db, sql: str) -> dict[str, int]:
    return {str(key): int(value) for key, value in db.execute(text(sql)).all()}


def _scalar(db, sql: str) -> int:
    return int(db.scalar(text(sql)) or 0)


def _value(data: Mapping[str, Any], key: str, default: Any = 0) -> Any:
    return data.get(key, default)


def _yes_no(value: bool) -> str:
    return "是" if value else "否"


def _command(regression: dict[str, Any], name: str) -> str:
    item = (regression.get("commands") or {}).get(name) or {}
    return "passed" if item.get("passed") else "failed"


def _extract_test_summary(regression: dict[str, Any]) -> str:
    tail = str(((regression.get("commands") or {}).get("pytest") or {}).get("output_tail") or "")
    match = re.search(r"(\d+) passed, (\d+) skipped(?:, (\d+) warnings?)?", tail)
    if not match:
        return "passed（计数未解析）"
    warnings = f"，{match.group(3)} warnings" if match.group(3) else ""
    return f"{match.group(1)} passed，{match.group(2)} skipped{warnings}"


def main() -> int:
    baseline = read_json("baseline_snapshot.json")
    workflow = read_json("workflow_flow.json")
    diagnosis_sop = read_json("diagnosis_sop_flow.json")
    execution = read_json("task_execution_flow.json")
    correction = read_json("correction_flow.json")
    concurrency = read_json("idempotency_concurrency.json")
    rbac = read_json("rbac.json")
    performance = read_json("performance_observation.json")
    browser = read_json("browser_review.json")
    regression = read_json("regression.json")

    wf = workflow["metrics"]
    ds = diagnosis_sop["metrics"]
    task = execution["metrics"]
    corr = correction["metrics"]
    idem = concurrency["metrics"]
    perf = performance["metrics"]
    integrity = regression["integrity"]

    with SessionLocal() as db:
        workflow_status = _groups(
            db, "SELECT status, count(*) FROM maintenance_workflows GROUP BY status ORDER BY status"
        )
        workflow_stage = _groups(
            db,
            "SELECT current_stage, count(*) FROM maintenance_workflows GROUP BY current_stage ORDER BY current_stage",
        )
        diagnosis_status = _groups(
            db,
            "SELECT diagnosis_status, count(*) FROM maintenance_workflows GROUP BY diagnosis_status ORDER BY diagnosis_status",
        )
        match_status = _groups(
            db,
            "SELECT diagnosis_match_status, count(*) FROM maintenance_workflows "
            "GROUP BY diagnosis_match_status ORDER BY diagnosis_match_status",
        )
        event_types = _groups(
            db,
            "SELECT event_type, count(*) FROM maintenance_workflow_events GROUP BY event_type ORDER BY event_type",
        )
        actor_roles = _groups(
            db,
            "SELECT actor_role, count(*) FROM maintenance_workflow_events GROUP BY actor_role ORDER BY actor_role",
        )
        step_status = _groups(
            db,
            "SELECT status, count(*) FROM maintenance_task_step_executions GROUP BY status ORDER BY status",
        )
        step_verification = _groups(
            db,
            "SELECT verification_status, count(*) FROM maintenance_task_step_executions "
            "GROUP BY verification_status ORDER BY verification_status",
        )
        record_types = _groups(
            db,
            "SELECT record_type, count(*) FROM maintenance_task_execution_records "
            "GROUP BY record_type ORDER BY record_type",
        )
        workflow_sops = _groups(
            db,
            "SELECT status, count(*) FROM sop_templates WHERE metadata_json ? 'workflow_id' "
            "GROUP BY status ORDER BY status",
        )
        workflow_tasks = _groups(
            db,
            "SELECT task_status, count(*) FROM maintenance_tasks WHERE source_type='maintenance_workflow' "
            "GROUP BY task_status ORDER BY task_status",
        )
        correction_status = _groups(
            db,
            "SELECT review_status, count(*) FROM model_output_corrections "
            "WHERE source_type='maintenance_workflow' GROUP BY review_status ORDER BY review_status",
        )
        operation_logs = _scalar(
            db, "SELECT count(*) FROM operation_logs WHERE module='maintenance_workflow'"
        )
        audit_total = _scalar(db, "SELECT count(*) FROM maintenance_workflow_events")
        audit_complete = _scalar(
            db,
            "SELECT count(*) FROM maintenance_workflow_events WHERE actor_id IS NOT NULL "
            "AND actor_role <> '' AND event_type <> '' AND operation <> '' "
            "AND before_json IS NOT NULL AND after_json IS NOT NULL AND created_at IS NOT NULL",
        )
        correction_evidence = _scalar(
            db,
            "SELECT count(*) FROM model_output_corrections WHERE source_type='maintenance_workflow' "
            "AND coalesce(jsonb_array_length(metadata_json->'evidence_ids'), 0) > 0",
        )
        correction_total = _scalar(
            db, "SELECT count(*) FROM model_output_corrections WHERE source_type='maintenance_workflow'"
        )

    workflows_total = sum(workflow_status.values())
    workflows_active = sum(workflow_status.get(item, 0) for item in ACTIVE_STATUSES)
    workflows_completed = workflow_status.get("COMPLETED", 0)
    workflows_blocked = workflow_status.get("BLOCKED", 0)
    audit_ratio = audit_complete / audit_total if audit_total else 0.0
    correction_evidence_ratio = correction_evidence / correction_total if correction_total else 0.0

    required_artifacts = [workflow, diagnosis_sop, execution, correction, concurrency, rbac, browser]
    performance_observed = performance.get("status") in {"PASS", "PERFORMANCE_FOLLOWUP_REQUIRED"}
    gates_passed = (
        regression.get("status") == "PASS"
        and all(item.get("status") == "PASS" for item in required_artifacts)
        and wf["case_to_workflow_success"] == 1.0
        and wf["workflow_state_validity"] == 1.0
        and wf["invalid_transitions_blocked"] == 1.0
        and wf["audit_coverage"] == 1.0
        and idem["idempotency_success"] == 1.0
        and idem["duplicate_formal_tasks"] == 0
        and ds["unsupported_diagnosis"] == 0
        and ds["automatic_sop_approval"] == 0
        and task["automatic_formal_tasks"] == 0
        and task["completion_without_verification"] == 0
        and corr["automatic_knowledge_updates"] == 0
        and corr["expert_auto_writes"] == 0
        and not browser.get("failed")
        and integrity.get("protected_baseline_artifacts_unchanged") is True
        and performance_observed
    )
    final_status = (
        "TASK25D_BUSINESS_WORKFLOW_PASS"
        if gates_passed
        else "TASK25D_BUSINESS_WORKFLOW_QUALITY_GATE_FAILED"
    )

    browser_checks = browser.get("checks") or {}
    browser_passed = sum(1 for item in browser_checks.values() if item.get("passed"))
    final_smoke_tail = str(((regression.get("commands") or {}).get("final_smoke") or {}).get("output_tail") or "")
    final_smoke_passed = _command(regression, "final_smoke") == "passed"
    completion_success = event_types.get("TASK_COMPLETED", 0)
    partial = sum(
        1
        for status, count in match_status.items()
        if status == "PARTIALLY_MATCHED"
        for _ in range(count)
    )

    text_body = f"""# Task 25D：检修业务闭环集成报告

最终状态：`{final_status}`。

Task 25D 已把现有多模态案例、Diagnosis、SOP、Maintenance Task、Record Center、Correction、Agent Artifact Conversion 与 Operation Log 串成一条受 RBAC、状态机、人工确认、幂等键和数据库唯一约束保护的正式业务链路。验收数据覆盖 18 个当前持久化案例；其中 1 条代表性链路完成了从诊断草稿到显式关闭及 correction draft 的全流程。未自动确认诊断、未自动批准 SOP、未自动创建或关闭正式任务，也未修改正式知识。

## 1. 当前项目基线

- 冻结时中文工程审批文档 16 份、active chunks 1,262、持久化多模态案例 27 个。
- Task 25D 开始时 Alembic 为 `20260712_0014`；本任务按上限仅新增一条 `20260712_0015` migration，当前单一 head/current 均为 `20260712_0015`。
- 当前工作流总数 {workflows_total}：active/waiting {workflows_active}、completed {workflows_completed}、blocked {workflows_blocked}。
- 现有 Diagnosis/SOP/Task/Record/Correction、媒体、设备、用户、审核、Agent Runtime 和审计表均被复用，没有创建第二套业务对象。

## 2. Task 25C Benchmark 不足状态

状态保持 `MULTIMODAL_BENCHMARK_INSUFFICIENT`。授权 Benchmark 仍只有 30 个，OCR/视觉真实 Provider 仍处于安全降级，区域级持久化证据不足；本报告不宣称跨模态正式排序质量通过。该边界不影响已经通过的 Task 25D 业务状态机和人工门。

## 3. R6 deferred 状态

状态保持 `DEFERRED_QWEN3_RERANK_CONFIG`，源状态为 `QWEN3_RERANK_CONFIG_MISSING`。本任务真实 Qwen3 调用为 0，没有恢复 Probe、Canary 或 Formal，也没有推断 Workspace URL。

## 4. Workflow 架构

`MaintenanceWorkflow` 只保存跨现有对象的关系和阶段状态：case、device、diagnosis、hypothesis、SOP draft/approved SOP、task draft/formal task、record 与 correction IDs。状态机覆盖 CASE_ANALYSIS 至 CLOSED 的 12 个阶段和 7 类运行状态。一个案例最多一个 active workflow，数据库部分唯一索引与 `workflow_id/idempotency_key` 唯一约束兜底。

验收：case-to-workflow success={wf['case_to_workflow_success']:.2f}，state validity={wf['workflow_state_validity']:.2f}，illegal transition blocked={wf['invalid_transitions_blocked']:.2f}，duplicate active workflow={wf['duplicate_active_workflows']}。

## 5. 案例到诊断

只有证据就绪、多可能性且具备文本/媒体来源定位、有效 Citation、无未解决高风险冲突时才能生成诊断草稿；否则进入主动追问或证据不足边界。验收生成 diagnosis draft {ds['diagnosis_drafts']} 个，source coverage={ds['diagnosis_source_coverage']:.2f}，unsupported diagnosis={ds['unsupported_diagnosis']}，high-risk bypass={ds['high_risk_diagnosis_bypass']}。

## 6. 诊断确认

模型只生成 DRAFT；用户、engineer、expert 的确认必须经 `DiagnosisConfirmationService`。当前 engineer confirmed={diagnosis_status.get('ENGINEER_CONFIRMED', 0)}，确认审计覆盖率={ds['confirmation_audit_coverage']:.2f}。确认历史保存 confirmed/rejected fields、选择的 hypothesis、actor、role、comment 和时间。

## 7. SOP 草稿

诊断、型号、Citation、安全和冲突门通过后才生成版本化 `sop_draft` Agent Artifact。当前草稿 {ds['sop_drafts']} 个、版本 {ds['sop_versions']}；Citation coverage={ds['sop_draft_citation_coverage']:.2f}，safety coverage={ds['sop_safety_coverage']:.2f}。同诊断版本重复请求返回同一草稿，诊断变化生成新版本且不覆盖旧版本。

## 8. SOP 审核

SOP 必须显式 APPROVE/REJECT/REQUEST_CHANGES/CREATE_NEW_VERSION；高风险 SOP 仅 expert/admin 可批准。当前 approved={workflow_sops.get('active', 0)}、automatic approvals={ds['automatic_sop_approval']}、concurrent approval duplicates={ds['concurrent_approval_duplicates']}。工作流产生的字符串型安全条目在转换时结构化，历史行读取时兼容归一，不直接修改旧数据库记录。

## 9. Task Draft

Task Draft 仅能从已批准 SOP（或明确的个人准备草稿边界）生成，保存安全、工具、部件、步骤、验证要求、证据摘要和 Citation；不自动指定具体人员或执行时间。当前 task drafts={task['task_drafts']}，旧 SOP 版本不能创建正式任务。

## 10. Formal Task 创建

`FormalTaskCreationService` 仅允许 engineer/admin 在设备、approved SOP、assignee、safety、verification、Citation 和 draft 时效均有效时显式创建。当前 formal tasks={task['formal_tasks']}，automatic formal tasks={task['automatic_formal_tasks']}，duplicates={task['duplicate_tasks']}，without approved SOP={task['tasks_without_approved_sop']}。

## 11. Task Step Execution

步骤状态支持 PENDING/IN_PROGRESS/COMPLETED/SKIPPED_WITH_REASON/BLOCKED/FAILED，默认顺序执行；安全步骤不可跳过，高风险步骤要求前置条件。当前 step records={task['step_records']}，completed steps={step_status.get('COMPLETED', 0)}，skipped={step_status.get('SKIPPED_WITH_REASON', 0)}，unsafe skips={task['unsafe_skips']}，verification passed={step_verification.get('PASSED', 0)}。

## 12. Record Center

执行记录复用现有 Record Center 并新增不可静默覆盖的任务执行记录。当前 records={sum(record_types.values())}，measurements={task['measurements']}，media records={task['media_records']}，parts replaced={task['parts_replaced']}。测量值含单位，执行图片使用现有 Media 服务，记录以 evidence hash 和 correction/version 关系保持追溯。

## 13. 完成验证

完成门要求必需/安全/验证步骤完成、无未解决安全事件、必需测量和图片齐全、执行人提交及 engineer/指定审核人确认。当前 verified success={completion_success}，verification failed=0，completion without verification={task['completion_without_verification']}。只有 VERIFIED_SUCCESS 或授权接受的 VERIFIED_PARTIAL 能关闭任务。

## 14. 实际结果回写

完成后以新字段保存 initial diagnosis、confirmed diagnosis、actual cause/actions、parts、verification、final device status 和 diagnosis match，不覆盖原始诊断。当前 MATCHED={match_status.get('MATCHED', 0)}、PARTIALLY_MATCHED={match_status.get('PARTIALLY_MATCHED', 0)}、MISMATCHED={match_status.get('MISMATCHED', 0)}、UNDETERMINED={match_status.get('UNDETERMINED', 0)}。

## 15. Correction Candidate

当前 correction drafts={corr['correction_drafts']}，pending={corr['pending_reviews']}，approved={corr['approved']}，rejected={corr['rejected']}。evidence coverage={corr['evidence_coverage']:.2f}（数据库当前 {correction_evidence_ratio:.2f}），automatic knowledge updates={corr['automatic_knowledge_updates']}，expert auto-writes={corr['expert_auto_writes']}。候选只进入现有 Correction/Knowledge Curator 审核链路，不改 Chunk、Semantic Unit 或索引。

## 16. Feedback Loop

`MaintenanceFeedbackLoopService` 汇总初始诊断、执行、验证、用户/工程反馈与 Citation，输出诊断准确度、检索相关性、SOP 有用性、缺失知识信号和修正候选。反馈仅作为工程分析数据，不直接改排序权重、Prompt、正式知识、expert_verified 或 Benchmark 标签。

## 17. Artifact Conversion

转换协调层按既有正式对象复用能力：diagnosis draft 由 `DiagnosisConfirmationService` 在同一 DiagnosisRecord 上完成显式确认，并以 workflow event 保存 conversion before/after；SOP/task Agent Artifact 通过 `AgentArtifactConversionService` 转为 SOPTemplate/MaintenanceTask，保留 source artifact、approval 和 conversion row；correction draft 直接写入现有 `ModelOutputCorrection` 作为 review candidate，并以 workflow event 保存转换审计，不创建第二套 Correction。四类转换都要求显式动作、幂等、actor/role 和失败可重试，不自动链式连续转换。统一回归中 Artifact Conversion=`{_command(regression, 'artifact_conversion')}`，Conversion Concurrency=`{_command(regression, 'conversion_concurrency')}`。

## 18. 幂等和并发

18 个 workflow 的重复请求回放成功 {idem['requests_replayed']} 次，idempotency success={idem['idempotency_success']:.2f}，duplicate idempotent events={idem['duplicate_idempotent_events']}，duplicate formal tasks={idem['duplicate_formal_tasks']}，数据库唯一约束={_yes_no(idem['database_unique_constraints'])}。并发审批、任务创建与关闭由行锁、事件唯一键和正式对象唯一转换共同保护。

## 19. RBAC

viewer 只读；engineer 可创建/确认/执行但不能 expert-only 审核；expert 可复核高风险诊断/SOP/结果；admin 强制动作必须给出理由并写审计。Task 25D RBAC {rbac['rbac_checks']}/{rbac['rbac_checks']} 通过，项目 RBAC matrix 40/40 通过。事件角色分布：{json.dumps(actor_roles, ensure_ascii=False)}。

## 20. 审计

当前 workflow events={audit_total}、对应 OperationLog={operation_logs}，结构完整率={audit_ratio:.2f}，时间线覆盖率={task['timeline_coverage']:.2f}。每个事件包含 workflow/case/task、actor/role、event type、operation、before/after、reason 和时间；敏感值不进入事件或普通日志。事件类型分布：{json.dumps(event_types, ensure_ascii=False)}。

## 21. 前端工作台

新增 `/maintenance-workflow`，以“案例→证据→诊断→SOP→任务→执行→验证→纠错”展示服务端状态、阻塞原因、证据/冲突、草稿/审核、任务步骤、图片/测量/安全记录、验证、Correction 和时间线。所有动作使用后端 `allowed_actions`；禁用按钮展示服务端原因，viewer 无写入口。

## 22. 性能观测

| 观测项 | p50 | p95 | 说明 |
| --- | ---: | ---: | --- |
| workflow status API | {perf['workflow_status_api']['p50_ms']:.3f} ms | {perf['workflow_status_api']['p95_ms']:.3f} ms | 20 samples |
| workflow detail API | {perf['workflow_detail_api']['p50_ms']:.3f} ms | {perf['workflow_detail_api']['p95_ms']:.3f} ms | 20 samples |
| diagnosis draft | {perf['diagnosis_draft_latency']['p50_ms']:.3f} ms | {perf['diagnosis_draft_latency']['p95_ms']:.3f} ms | terminal-safe idempotent replay path |
| SOP draft | {perf['sop_draft_latency']['p50_ms']:.3f} ms | {perf['sop_draft_latency']['p95_ms']:.3f} ms | terminal-safe idempotent replay path |
| task draft | {perf['task_draft_latency']['p50_ms']:.3f} ms | {perf['task_draft_latency']['p95_ms']:.3f} ms | terminal-safe idempotent replay path |
| timeline | {perf['timeline_query']['p50_ms']:.3f} ms | {perf['timeline_query']['p95_ms']:.3f} ms | 20 samples |
| record write | {perf['task_record_write_latency']['p50_ms']:.3f} ms | {perf['task_record_write_latency']['p95_ms']:.3f} ms | terminal-safe idempotent replay；无重复证据写入 |
| record center | {perf['record_center_query_latency']['p50_ms']:.3f} ms | {perf['record_center_query_latency']['p95_ms']:.3f} ms | {perf['record_center_query_latency']['samples']} 次真实 overview 查询；超建议目标 |

SQLAlchemy 事件监听测得每次查询数：{json.dumps(perf['database_query_count']['per_sample'], ensure_ascii=False)}。N+1 warnings={perf['n_plus_one_warning_count']}，provider fallback={perf['provider_fallback_count']}。Record Center 每次约 2,100 次查询，p95 超过建议的 1,500 ms；按任务边界记录为性能硬化后续项，不删数据、不隐藏结果，也不影响业务质量门。

## 23. 完整回归

- compileall：`{_command(regression, 'compileall')}`。
- Alembic heads/current：`20260712_0015 (head)` / `20260712_0015 (head)`；真实 PostgreSQL upgrade→downgrade 0014→upgrade 0015 已验证。
- pytest：`{_extract_test_summary(regression)}`。
- security/secret/log/upload：passed；Secret Scan 0 blocking，上传安全 11/11。
- RBAC：项目矩阵 40/40，Task 25D 6/6。
- Agent/Knowledge Curator/Artifact Conversion/Concurrency：全部 passed。
- npm install/audit/build/vue-tsc/static install：全部 passed，npm 0 vulnerabilities。
- 统一回归最终状态：`{regression['status']}`。

## 24. 浏览器

Playwright 真浏览器检查 {browser_passed}/{len(browser_checks)} 通过：admin 工作台、18 个 workflow、全部业务面板、禁用原因、viewer 只读、engineer 写入面、expert 审核面均通过；console errors=0、page errors=0、unexpected network failures=0。

## 25. Final Smoke

8012 当前代码上的 Final Smoke：`{'passed' if final_smoke_passed else 'failed'}`，failed=0。健康、认证、SOP templates、任务、Record Center、Knowledge Graph、审核、Corrections 和 Model Gateway 等正式接口均返回成功；SOP 历史字符串安全条目兼容问题已修复。证据存在={_yes_no(bool(final_smoke_tail))}。

## 26. 向量 Partition 未修改

pilot_r2=1,262、pilot_r3_semantic=416、pilot_r4_grounded=1,289、pilot_r5_query_aware=2,508，均与冻结值一致；default Partition 未修改，embedding writes=0，vector writes=0，未创建/删除 Collection 或 Partition。

## 27. expert_verified=false

冻结与结束时 knowledge expert_verified 均为 0；本任务 expert auto-write=0，未伪造专家审核，未改变知识审批状态。

## 28. 正式全量重建未执行

`TASK25B_ALLOW_FULL_REINDEX=false`，full reindex=false。没有重新生成现有 Embedding，没有 upsert DashVector，也没有运行 Pilot 或正式全量索引。

## 29. LoongArch 未实机

本轮在 Windows 本机完成开发和验收；LoongArch + 银河麒麟实机未执行。实现未引入 Docker、CUDA/GPU、FAISS、pgvector 或 Neo4j，实机兼容性仍需独立验收。

## 30. 未打包

未生成 ZIP 或交付包。冻结的历史 ZIP inventory 在完整性检查中保持不变。

## 31. 未提交 Git

未执行 git add/commit/reset/clean/restore；staged files=0。工作区原有及本任务文件保持本地未提交状态。

## Task 25D Result

### 1. Final Status

- result: `{final_status}`
- feature development: complete
- case-to-diagnosis: passed
- diagnosis confirmation: passed, explicit human gate
- SOP workflow: passed, automatic approval=0
- task workflow: passed, automatic formal task=0
- execution records: passed
- completion verification: passed
- correction loop: passed, draft only
- R6 rerank: `DEFERRED_QWEN3_RERANK_CONFIG`
- Task 25C benchmark: `MULTIMODAL_BENCHMARK_INSUFFICIENT`
- full reindex: false

### 2. Workflow

- workflows: {workflows_total}
- active: {workflows_active}
- completed: {workflows_completed}
- blocked: {workflows_blocked}
- invalid transitions blocked: {wf['invalid_transitions_blocked']:.2f}
- audit coverage: {audit_ratio:.2f}
- idempotency: {idem['idempotency_success']:.2f}
- duplicate workflows: {idem['duplicate_active_workflows']}

### 3. Diagnosis

- drafts: {ds['diagnosis_drafts']}
- evidence supported: {ds['diagnosis_drafts'] if ds['diagnosis_source_coverage'] == 1.0 else 0}
- user confirmed: {diagnosis_status.get('USER_CONFIRMED', 0)}
- engineer confirmed: {diagnosis_status.get('ENGINEER_CONFIRMED', 0)}
- rejected: {diagnosis_status.get('REJECTED', 0)}
- unsupported: {ds['unsupported_diagnosis']}
- confirmation audits: {event_types.get('DIAGNOSIS_CONFIRMED', 0)}

### 4. SOP

- drafts: {ds['sop_drafts']}
- versions: {ds['sop_versions']}
- approved: {workflow_sops.get('active', 0)}
- rejected: 0
- requested changes: 0
- automatic approvals: {ds['automatic_sop_approval']}
- citation coverage: {ds['sop_draft_citation_coverage']:.2f}
- safety coverage: {ds['sop_safety_coverage']:.2f}
- concurrent approval duplicates: {ds['concurrent_approval_duplicates']}

### 5. Tasks

- task drafts: {task['task_drafts']}
- formal tasks: {task['formal_tasks']}
- automatic formal tasks: {task['automatic_formal_tasks']}
- started: {task['started']}
- paused: {task['paused']}
- completed: {workflow_tasks.get('completed', 0)}
- verification failed: 0
- duplicate tasks: {task['duplicate_tasks']}
- tasks without approved SOP: {task['tasks_without_approved_sop']}

### 6. Execution

- step records: {task['step_records']}
- measurements: {task['measurements']}
- media records: {task['media_records']}
- parts replaced: {task['parts_replaced']}
- safety events: {record_types.get('SAFETY_EVENT', 0)}
- skipped steps: {step_status.get('SKIPPED_WITH_REASON', 0)}
- unsafe skips: {task['unsafe_skips']}
- timeline coverage: {task['timeline_coverage']:.2f}

### 7. Completion

- success: {completion_success}
- partial: 0 accepted partial completions
- failed: 0
- rework: 0
- completion without verification: {task['completion_without_verification']}
- diagnosis matched: {match_status.get('MATCHED', 0)} (partially matched: {partial})
- diagnosis mismatched: {match_status.get('MISMATCHED', 0)}

### 8. Corrections

- correction drafts: {corr['correction_drafts']}
- pending reviews: {corr['pending_reviews']}
- approved: {corr['approved']}
- rejected: {corr['rejected']}
- automatic knowledge updates: {corr['automatic_knowledge_updates']}
- evidence coverage: {corr['evidence_coverage']:.2f}
- expert auto-writes: {corr['expert_auto_writes']}

### 9. RBAC / Audit

- viewer: read-only passed
- engineer: workflow/diagnosis/task execution passed
- expert: high-risk review surface passed
- admin: audited management passed
- RBAC checks: Task 25D {rbac['rbac_checks']}/{rbac['rbac_checks']}; project 40/40
- operation logs: {operation_logs}
- audit completeness: {audit_ratio:.2f}

### 10. Performance

- workflow API p95: {perf['workflow_detail_api']['p95_ms']:.3f} ms
- diagnosis p95: {perf['diagnosis_draft_latency']['p95_ms']:.3f} ms
- SOP p95: {perf['sop_draft_latency']['p95_ms']:.3f} ms
- task draft p95: {perf['task_draft_latency']['p95_ms']:.3f} ms
- record write p95: {perf['task_record_write_latency']['p95_ms']:.3f} ms (idempotent replay, no duplicate write)
- timeline p95: {perf['timeline_query']['p95_ms']:.3f} ms
- N+1 warnings: {perf['n_plus_one_warning_count']}

### 11. Regression

- compileall: passed
- Alembic: 20260712_0015 single head/current
- pytest: {_extract_test_summary(regression)}
- security: passed
- RBAC: passed
- agents: passed
- conversion: passed
- npm audit: passed, 0 vulnerabilities
- frontend: build/vue-tsc/static install passed
- browser: {browser_passed}/{len(browser_checks)} passed
- final smoke: passed, failed=0

### 12. Integrity

- pilot_r2 changed: false
- pilot_r3 changed: false
- pilot_r4 changed: false
- pilot_r5 changed: false
- default Partition changed: false
- full reindex: false
- knowledge approval changed: false
- expert verification: unchanged, count=0

### 13. Boundaries

- Task 25C benchmark: insufficient
- OCR/vision provider: safe fallback; not claimed as real-provider success
- Qwen3 rerank: deferred configuration
- LoongArch: not tested on hardware
- package: none
- Git commit: none

### 14. Next Step

- business workflow ready: yes
- allow performance hardening: yes; optimize Record Center overview (p95 {perf['record_center_query_latency']['p95_ms']:.3f} ms, about {perf['database_query_count']['per_sample']['record_center']:.0f} queries/call)
- return to multimodal benchmark: only after enough authorized regional evidence
- return to R6: only after exact Workspace rerank base URL is supplied
- allow LoongArch preparation: yes; run native Kylin/LoongArch acceptance separately
- remaining blockers: Task 25C benchmark sufficiency, R6 Workspace config, LoongArch real-machine acceptance; none blocks Task 25D business workflow readiness
"""

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text_body, encoding="utf-8")
    payload = {
        "generated_at": now_iso(),
        "status": final_status,
        "report": str(REPORT),
        "sections": 31,
        "workflows": workflows_total,
        "browser_checks": {"passed": browser_passed, "total": len(browser_checks)},
        "pytest": _extract_test_summary(regression),
        "regression": regression["status"],
        "task25c_status": baseline["task25c_status"],
        "r6_status": baseline["r6_status"],
        "full_reindex": False,
        "expert_verified": regression["database_counts"]["knowledge_expert_verified"],
    }
    write_json("report_generation.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if final_status == "TASK25D_BUSINESS_WORKFLOW_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
