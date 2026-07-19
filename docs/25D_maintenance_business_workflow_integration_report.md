# Task 25D：检修业务闭环集成报告

最终状态：`TASK25D_BUSINESS_WORKFLOW_PASS`。

Task 25D 已把现有多模态案例、Diagnosis、SOP、Maintenance Task、Record Center、Correction、Agent Artifact Conversion 与 Operation Log 串成一条受 RBAC、状态机、人工确认、幂等键和数据库唯一约束保护的正式业务链路。验收数据覆盖 18 个当前持久化案例；其中 1 条代表性链路完成了从诊断草稿到显式关闭及 correction draft 的全流程。未自动确认诊断、未自动批准 SOP、未自动创建或关闭正式任务，也未修改正式知识。

## 1. 当前项目基线

- 冻结时中文工程审批文档 16 份、active chunks 1,262、持久化多模态案例 27 个。
- Task 25D 开始时 Alembic 为 `20260712_0014`；本任务按上限仅新增一条 `20260712_0015` migration，当前单一 head/current 均为 `20260712_0015`。
- 当前工作流总数 18：active/waiting 17、completed 1、blocked 0。
- 现有 Diagnosis/SOP/Task/Record/Correction、媒体、设备、用户、审核、Agent Runtime 和审计表均被复用，没有创建第二套业务对象。

## 2. Task 25C Benchmark 不足状态

状态保持 `MULTIMODAL_BENCHMARK_INSUFFICIENT`。授权 Benchmark 仍只有 30 个，OCR/视觉真实 Provider 仍处于安全降级，区域级持久化证据不足；本报告不宣称跨模态正式排序质量通过。该边界不影响已经通过的 Task 25D 业务状态机和人工门。

## 3. R6 deferred 状态

状态保持 `DEFERRED_QWEN3_RERANK_CONFIG`，源状态为 `QWEN3_RERANK_CONFIG_MISSING`。本任务真实 Qwen3 调用为 0，没有恢复 Probe、Canary 或 Formal，也没有推断 Workspace URL。

## 4. Workflow 架构

`MaintenanceWorkflow` 只保存跨现有对象的关系和阶段状态：case、device、diagnosis、hypothesis、SOP draft/approved SOP、task draft/formal task、record 与 correction IDs。状态机覆盖 CASE_ANALYSIS 至 CLOSED 的 12 个阶段和 7 类运行状态。一个案例最多一个 active workflow，数据库部分唯一索引与 `workflow_id/idempotency_key` 唯一约束兜底。

验收：case-to-workflow success=1.00，state validity=1.00，illegal transition blocked=1.00，duplicate active workflow=0。

## 5. 案例到诊断

只有证据就绪、多可能性且具备文本/媒体来源定位、有效 Citation、无未解决高风险冲突时才能生成诊断草稿；否则进入主动追问或证据不足边界。验收生成 diagnosis draft 1 个，source coverage=1.00，unsupported diagnosis=0，high-risk bypass=0。

## 6. 诊断确认

模型只生成 DRAFT；用户、engineer、expert 的确认必须经 `DiagnosisConfirmationService`。当前 engineer confirmed=1，确认审计覆盖率=1.00。确认历史保存 confirmed/rejected fields、选择的 hypothesis、actor、role、comment 和时间。

## 7. SOP 草稿

诊断、型号、Citation、安全和冲突门通过后才生成版本化 `sop_draft` Agent Artifact。当前草稿 1 个、版本 1；Citation coverage=1.00，safety coverage=1.00。同诊断版本重复请求返回同一草稿，诊断变化生成新版本且不覆盖旧版本。

## 8. SOP 审核

SOP 必须显式 APPROVE/REJECT/REQUEST_CHANGES/CREATE_NEW_VERSION；高风险 SOP 仅 expert/admin 可批准。当前 approved=1、automatic approvals=0、concurrent approval duplicates=0。工作流产生的字符串型安全条目在转换时结构化，历史行读取时兼容归一，不直接修改旧数据库记录。

## 9. Task Draft

Task Draft 仅能从已批准 SOP（或明确的个人准备草稿边界）生成，保存安全、工具、部件、步骤、验证要求、证据摘要和 Citation；不自动指定具体人员或执行时间。当前 task drafts=1，旧 SOP 版本不能创建正式任务。

## 10. Formal Task 创建

`FormalTaskCreationService` 仅允许 engineer/admin 在设备、approved SOP、assignee、safety、verification、Citation 和 draft 时效均有效时显式创建。当前 formal tasks=1，automatic formal tasks=0，duplicates=0，without approved SOP=0。

## 11. Task Step Execution

步骤状态支持 PENDING/IN_PROGRESS/COMPLETED/SKIPPED_WITH_REASON/BLOCKED/FAILED，默认顺序执行；安全步骤不可跳过，高风险步骤要求前置条件。当前 step records=1，completed steps=1，skipped=0，unsafe skips=0，verification passed=1。

## 12. Record Center

执行记录复用现有 Record Center 并新增不可静默覆盖的任务执行记录。当前 records=7，measurements=1，media records=2，parts replaced=0。测量值含单位，执行图片使用现有 Media 服务，记录以 evidence hash 和 correction/version 关系保持追溯。

## 13. 完成验证

完成门要求必需/安全/验证步骤完成、无未解决安全事件、必需测量和图片齐全、执行人提交及 engineer/指定审核人确认。当前 verified success=1，verification failed=0，completion without verification=0。只有 VERIFIED_SUCCESS 或授权接受的 VERIFIED_PARTIAL 能关闭任务。

## 14. 实际结果回写

完成后以新字段保存 initial diagnosis、confirmed diagnosis、actual cause/actions、parts、verification、final device status 和 diagnosis match，不覆盖原始诊断。当前 MATCHED=0、PARTIALLY_MATCHED=1、MISMATCHED=0、UNDETERMINED=17。

## 15. Correction Candidate

当前 correction drafts=1，pending=0，approved=0，rejected=0。evidence coverage=1.00（数据库当前 1.00），automatic knowledge updates=0，expert auto-writes=0。候选只进入现有 Correction/Knowledge Curator 审核链路，不改 Chunk、Semantic Unit 或索引。

## 16. Feedback Loop

`MaintenanceFeedbackLoopService` 汇总初始诊断、执行、验证、用户/工程反馈与 Citation，输出诊断准确度、检索相关性、SOP 有用性、缺失知识信号和修正候选。反馈仅作为工程分析数据，不直接改排序权重、Prompt、正式知识、expert_verified 或 Benchmark 标签。

## 17. Artifact Conversion

转换协调层按既有正式对象复用能力：diagnosis draft 由 `DiagnosisConfirmationService` 在同一 DiagnosisRecord 上完成显式确认，并以 workflow event 保存 conversion before/after；SOP/task Agent Artifact 通过 `AgentArtifactConversionService` 转为 SOPTemplate/MaintenanceTask，保留 source artifact、approval 和 conversion row；correction draft 直接写入现有 `ModelOutputCorrection` 作为 review candidate，并以 workflow event 保存转换审计，不创建第二套 Correction。四类转换都要求显式动作、幂等、actor/role 和失败可重试，不自动链式连续转换。统一回归中 Artifact Conversion=`passed`，Conversion Concurrency=`passed`。

## 18. 幂等和并发

18 个 workflow 的重复请求回放成功 18 次，idempotency success=1.00，duplicate idempotent events=0，duplicate formal tasks=0，数据库唯一约束=是。并发审批、任务创建与关闭由行锁、事件唯一键和正式对象唯一转换共同保护。

## 19. RBAC

viewer 只读；engineer 可创建/确认/执行但不能 expert-only 审核；expert 可复核高风险诊断/SOP/结果；admin 强制动作必须给出理由并写审计。Task 25D RBAC 6/6 通过，项目 RBAC matrix 40/40 通过。事件角色分布：{"admin": 25, "engineer": 8}。

## 20. 审计

当前 workflow events=33、对应 OperationLog=33，结构完整率=1.00，时间线覆盖率=1.00。每个事件包含 workflow/case/task、actor/role、event type、operation、before/after、reason 和时间；敏感值不进入事件或普通日志。事件类型分布：{"CASE_CREATED": 18, "CORRECTION_CREATED": 1, "DIAGNOSIS_CONFIRMED": 1, "DIAGNOSIS_DRAFTED": 1, "SOP_DRAFTED": 1, "SOP_REVIEWED": 1, "STEP_RECORDED": 2, "TASK_COMPLETED": 1, "TASK_CREATED": 1, "TASK_DRAFTED": 1, "TASK_RECORD_ADDED": 2, "TASK_STARTED": 1, "VERIFICATION_SUBMITTED": 1, "WORKFLOW_CLOSED": 1}。

## 21. 前端工作台

新增 `/maintenance-workflow`，以“案例→证据→诊断→SOP→任务→执行→验证→纠错”展示服务端状态、阻塞原因、证据/冲突、草稿/审核、任务步骤、图片/测量/安全记录、验证、Correction 和时间线。所有动作使用后端 `allowed_actions`；禁用按钮展示服务端原因，viewer 无写入口。

## 22. 性能观测

| 观测项 | p50 | p95 | 说明 |
| --- | ---: | ---: | --- |
| workflow status API | 1.481 ms | 9.394 ms | 20 samples |
| workflow detail API | 11.674 ms | 93.714 ms | 20 samples |
| diagnosis draft | 1.660 ms | 10.729 ms | terminal-safe idempotent replay path |
| SOP draft | 1.466 ms | 1.920 ms | terminal-safe idempotent replay path |
| task draft | 1.433 ms | 1.778 ms | terminal-safe idempotent replay path |
| timeline | 4.329 ms | 5.385 ms | 20 samples |
| record write | 1.264 ms | 1.407 ms | terminal-safe idempotent replay；无重复证据写入 |
| record center | 2598.262 ms | 3110.722 ms | 5 次真实 overview 查询；超建议目标 |

SQLAlchemy 事件监听测得每次查询数：{"diagnosis_draft": 2.0, "record_center": 2100.0, "sop_draft": 2.0, "task_draft": 2.0, "task_record_write": 2.0, "timeline": 2.0, "workflow_detail": 12.0, "workflow_status": 2.0}。N+1 warnings=1，provider fallback=0。Record Center 每次约 2,100 次查询，p95 超过建议的 1,500 ms；按任务边界记录为性能硬化后续项，不删数据、不隐藏结果，也不影响业务质量门。

## 23. 完整回归

- compileall：`passed`。
- Alembic heads/current：`20260712_0015 (head)` / `20260712_0015 (head)`；真实 PostgreSQL upgrade→downgrade 0014→upgrade 0015 已验证。
- pytest：`353 passed，3 skipped，4 warnings`。
- security/secret/log/upload：passed；Secret Scan 0 blocking，上传安全 11/11。
- RBAC：项目矩阵 40/40，Task 25D 6/6。
- Agent/Knowledge Curator/Artifact Conversion/Concurrency：全部 passed。
- npm install/audit/build/vue-tsc/static install：全部 passed，npm 0 vulnerabilities。
- 统一回归最终状态：`PASS`。

## 24. 浏览器

Playwright 真浏览器检查 25/25 通过：admin 工作台、18 个 workflow、全部业务面板、禁用原因、viewer 只读、engineer 写入面、expert 审核面均通过；console errors=0、page errors=0、unexpected network failures=0。

## 25. Final Smoke

8012 当前代码上的 Final Smoke：`passed`，failed=0。健康、认证、SOP templates、任务、Record Center、Knowledge Graph、审核、Corrections 和 Model Gateway 等正式接口均返回成功；SOP 历史字符串安全条目兼容问题已修复。证据存在=是。

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

- result: `TASK25D_BUSINESS_WORKFLOW_PASS`
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

- workflows: 18
- active: 17
- completed: 1
- blocked: 0
- invalid transitions blocked: 1.00
- audit coverage: 1.00
- idempotency: 1.00
- duplicate workflows: 0

### 3. Diagnosis

- drafts: 1
- evidence supported: 1
- user confirmed: 0
- engineer confirmed: 1
- rejected: 0
- unsupported: 0
- confirmation audits: 1

### 4. SOP

- drafts: 1
- versions: 1
- approved: 1
- rejected: 0
- requested changes: 0
- automatic approvals: 0
- citation coverage: 1.00
- safety coverage: 1.00
- concurrent approval duplicates: 0

### 5. Tasks

- task drafts: 1
- formal tasks: 1
- automatic formal tasks: 0
- started: 1
- paused: 0
- completed: 1
- verification failed: 0
- duplicate tasks: 0
- tasks without approved SOP: 0

### 6. Execution

- step records: 1
- measurements: 1
- media records: 2
- parts replaced: 0
- safety events: 0
- skipped steps: 0
- unsafe skips: 0
- timeline coverage: 1.00

### 7. Completion

- success: 1
- partial: 0 accepted partial completions
- failed: 0
- rework: 0
- completion without verification: 0
- diagnosis matched: 0 (partially matched: 1)
- diagnosis mismatched: 0

### 8. Corrections

- correction drafts: 1
- pending reviews: 0
- approved: 0
- rejected: 0
- automatic knowledge updates: 0
- evidence coverage: 1.00
- expert auto-writes: 0

### 9. RBAC / Audit

- viewer: read-only passed
- engineer: workflow/diagnosis/task execution passed
- expert: high-risk review surface passed
- admin: audited management passed
- RBAC checks: Task 25D 6/6; project 40/40
- operation logs: 33
- audit completeness: 1.00

### 10. Performance

- workflow API p95: 93.714 ms
- diagnosis p95: 10.729 ms
- SOP p95: 1.920 ms
- task draft p95: 1.778 ms
- record write p95: 1.407 ms (idempotent replay, no duplicate write)
- timeline p95: 5.385 ms
- N+1 warnings: 1

### 11. Regression

- compileall: passed
- Alembic: 20260712_0015 single head/current
- pytest: 353 passed，3 skipped，4 warnings
- security: passed
- RBAC: passed
- agents: passed
- conversion: passed
- npm audit: passed, 0 vulnerabilities
- frontend: build/vue-tsc/static install passed
- browser: 25/25 passed
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
- allow performance hardening: yes; optimize Record Center overview (p95 3110.722 ms, about 2100 queries/call)
- return to multimodal benchmark: only after enough authorized regional evidence
- return to R6: only after exact Workspace rerank base URL is supplied
- allow LoongArch preparation: yes; run native Kylin/LoongArch acceptance separately
- remaining blockers: Task 25C benchmark sufficiency, R6 Workspace config, LoongArch real-machine acceptance; none blocks Task 25D business workflow readiness
