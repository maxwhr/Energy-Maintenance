# Task 25A 赛题对标与全量代码审计报告

> 审计生成时间：2026-07-10T12:07:47.734052+00:00。扫描 tracked/untracked 文本源码；storage 只统计目录/数量，不读取用户内容；未调用真实外部 API；未打包、未提交 Git、未修改 migration。

## 1. Executive Summary

1. 当前整体成熟度：工程底座与传统业务闭环较成熟，但决定赛题竞争力的真实语义/跨模态检索、目标机部署与质量评估未达标。
2. 具备继续增量重构基础：是。分层、数据库、审核/转换、前端和专项脚本可保留。
3. 是否建议整体重写：否。整体重写会丢失已验证持久化和审计能力。
4. 是否建议局部重构：是，但主方案不是零散修补，而是关键主链路重构。
5. 最大赛题风险：LoongArch + 银河麒麟未实机验收，且仓库缺正式 systemd/Nginx 产物。
6. 最大技术风险：真实 embedding/DashVector/共享图文向量缺失，hybrid 仍是 fake/deterministic。
7. 最大性能风险：record center 对多表全量取数、内存排序后分页；并发 p95 1763.863 ms。
8. 最大演示风险：UI 可展示 mock/dry-run/real 状态，但若讲解不严谨会把历史 real-call、当前 blocked 和 mock 混为一谈。

**最终主方案：C. 关键主链路重构。**

## 2. Competition Hard Gates

| gate | judgment | evidence / risk |
|---|---|---|
| B/S | verified | FastAPI + Vue SPA，final smoke 静态入口与 API 通过 |
| LoongArch | partial / P0 | 静态审计 high_risk，无实机 |
| 银河麒麟 | partial / P0 | 无 V10/V11 安装、systemd、Nginx、权限证据 |
| PC Web | verified | 32 路由，build 与静态安装通过 |
| 云端/本地模型 | B | 云模型历史 real-call；本地 llama.cpp 仅预留 |
| 多模态 | B/C | OCR/MIMO 有历史 real-call；跨模态共享向量和相似图片检索缺失 |
| 知识检索 | A + D | 关键词/references verified；向量/hybrid 为 mock boundary |
| 标准化作业 | A/B/C | 结构化步骤/安全/工具可用；显式前置/禁止/中止 gate 不完整 |
| 知识沉淀 | A/B | 贡献、审核、KG、转换存在；修正回用和质量评分不足 |
| 人工修正 | A + E | 修正记录可追踪；accepted 结果不回流检索/规则 |

## 3. Requirement Traceability Summary

- verified：35
- implemented_but_not_fully_verified：27
- partial：13
- placeholder_or_mock：3
- missing：5

逐项 12 字段证据见 `docs/25A_competition_requirement_traceability_matrix.md` 与 `.runtime/task25a/requirement_traceability.json`。

## 4. Architecture Audit

- 生产主线基本遵循 api -> service -> repository -> model；174 个 FastAPI route decorators 均集中注册。
- API 层多数只做参数/权限/服务调用，但 system status 含直接 SQL，部分 route 各自重复 ok/fail helper。
- 事务通常由 service commit/rollback；repository 主要 flush/refresh。Agent artifact conversion 有数据库唯一约束和并发防重。
- 当前 42 张表、8 个 migration，model metadata 与 current 20260601_0008 可启动。
- 生产代码发现 12 处 broad Exception，多数位于 adapter/parser/安全边界；需要逐项确认是否保留足够错误码与可观测性。
- 未发现 Docker 正式路线；没有 deploy/、systemd .service 或 Nginx .conf，是部署硬缺口。

## 5. Backend Audit

- 后端生产代码：189 文件 / 35001 行。
- 分层、分页、RBAC、PostgreSQL 持久化总体清晰；42 表真实存在。
- RecordCenterRepository._collect_items 对最多 11 种记录分别全量读取，再 Python 排序/分页，数据增长后是明确瓶颈。
- RetrievalRepository 使用多字段 ILIKE 和 JSONB cast，candidate_limit=100 可控但会随文档规模放大扫描成本。
- JSONB 广泛用于 steps/references/context/log/artifact；当前索引以 BTree 为主，需按真实查询再决定 GIN，不能盲加。
- Auth logout 是无状态成功返回，不撤销 JWT；生产需短时 token、刷新/撤销或等价策略。
- Adapter broad exception 会清洗外部错误，但必须避免把 provider 失败变成业务伪成功；现有 diagnostics/fallback 字段值得保留。

## 6. Frontend Audit

- 前端生产代码：102 文件 / 13780 行；32 个路由。
- Axios 统一 baseURL=/api；源码中无 127.0.0.1 硬编码、console.log、debugger、v-html、innerHTML 或显式 any。
- 角色路由与菜单覆盖 admin/expert/engineer/viewer；40 项后端 RBAC 脚本通过。
- mock 相关词 87 处、dry-run 29 处、fallback 17 处，主要用于诚实展示边界；比赛 UI 应把技术细节折叠，避免误解。
- 静态扫描发现 24 个死代码/未引用候选，含 3 个 API 模块和若干图片；动态路由/导入存在，Task 25A 不处理。
- 本轮没有浏览器人工走查，不能仅凭 build 认定视觉、交互、无障碍完全达标。

## 7. Multimodal Capability Audit

- 图片上传：verified；上传安全与 RBAC 当前通过。
- OCR：有 provider、job、结果、confidence、regions 与历史 real-call 证据；无准确率集。
- 视觉理解：有告警码、设备信息、视觉发现、可能故障、安全风险、建议和人工复核字段；无部位识别金标准。
- 多模态融合：能把 accepted/manual/real evidence 链接到 QA、诊断、SOP、Agent；本轮 flow 主要是 blocked/mock。
- 图像 embedding：不存在。文本与图像统一向量空间：不存在。相似图片检索：不存在。
- 图片到 chunk：支持人工 evidence link，但没有自动匹配排序/解释指标。
- 最终判断：真实 OCR/视觉为 B，融合为 B，跨模态匹配为 C，相似图检索为 E。

## 8. Retrieval and RAG Audit

- 上传 -> 安全 -> 解析 -> 清洗 -> 切分 -> 审核 -> 关键词召回 -> 引用 -> QA 记录闭环可用。
- 召回强制 parsed + active + approved document 和 active chunk，来源真实。
- 切分保存 section_title/page_number，但表格、图注、复杂标题层级保真无专项验收。
- 真实 embedding/DashVector 未闭环；30 条 vector index 全部 fake_in_memory + deterministic_test。
- hybrid merge 有权重、归一化、min score，但在真实向量缺失时只能算 D。
- 未发现独立 reranker 或真实检索评估集；query expansion 是规则词扩展，不是模型 rewrite。
- 关键词基线 4 次串行 p50=238.173 ms、p95=476.238 ms。
- 最终判断：可演示可信关键词检索，但未达到高精度语义/跨模态比赛竞争力。

## 9. Knowledge Base and Knowledge Graph Audit

- KG 包含 nodes、edges、aliases、evidence、extraction runs、candidates、审批与 node merge。
- 业务 context 已接入 retrieval、diagnosis、SOP，不只是展示。
- 节点 canonical + alias、边唯一检查和 merge 处理部分重复；缺统一版本/有效期/冲突决策记录。
- approved/parsed 文档和 approved/converted 贡献才能抽取候选，候选需审核；但 admin/expert 可直接手工建正式节点。
- 341 个 pending 候选显示质量/积压风险；缺批量语义去重与质量排序。
- 比赛展示可用，但必须强调 PostgreSQL 轻量 KG，不宣称完整自动知识图谱学习。

## 10. Diagnosis, SOP and Task Workflow Audit

- 诊断输出原因、步骤、安全、建议、引用、history/media/KG 并写 diagnosis_records。
- SOP 有步骤序号、expected result、safety、tools、materials、维护等级、版本、执行记录。
- 安全文本覆盖断电、验电、挂牌、监护与 PPE 类工具；缺显式 prerequisite、prohibited_actions、stop_conditions schema。
- SOP execution 支持 not_started -> in_progress -> completed/aborted，不能逆转。
- 任务 create/assign/start/complete/cancel、来源 trace、SOP/执行、媒体/维护记录可关联。
- Agent 草稿需要人工审批和显式转换，不自动执行高风险写操作；并发转换 5 请求只成功 1 条。

## 11. Feedback and Correction Loop Audit

- correction create/list/detail/resolve、source trace、before/after 和审核人可追踪。
- 数据库 accepted=8，但 converted_contribution_id 全为空。
- 未发现 accepted correction 自动/显式回用于 retrieval index、规则库或 prompt 版本。
- 结论：记录闭环 verified，学习/回用闭环 missing；Task 25C 优先。

## 12. Security Audit

- JWT/RBAC、上传安全、日志脱敏、请求体限制、进程内 rate limit、production config guard 已实现。
- 40 项 RBAC、11 项上传、日志脱敏和 secret scan 当前通过/附注。
- secret scan：3 个本机 .env configured note、0 blocking，未输出值；历史已暴露密钥仍必须轮换。
- development 当前 secret/admin password 未达生产标准；production guard 可拒绝弱配置。
- operation_logs=0，说明统一审计日志并未覆盖所有业务；专项 event/call/review 表存在但缺保留/防篡改策略。
- 进程内 rate limit 不适合多实例；本轮未做 429 专项行为测试。

## 13. Performance Baseline

- 端点：12；请求：93；错误率：0.0。
- 总体 p50=32.615 ms，p95=1233.407 ms，p99=1763.236 ms，max=1764.037 ms。
- record center 串行 p95=868.276 ms，并发 p95=1763.863 ms。
- KG context 串行 p95=155.447 ms，并发 p95=669.844 ms。
- 实际参数为 warmup=1、serial=4、read concurrency=5；低于脚本默认 5/20/5，避免 120 req/min 限流污染。
- 这不是四核 8GB/LoongArch 容量证明。日志表、JSONB、全表聚合、文件解析和 Agent 串行仍是风险。

## 14. Testing and Quality Gates

- compile、Alembic heads/current、13 个指定专项脚本、性能、npm audit/type/build、静态安装和 final smoke 均执行。
- secret scan 首轮被新脚本参数名误报 blocking，修正局部变量名后重跑为 passed_with_notes；未放宽扫描器。
- ruff/mypy 未配置；frontend 无 lint/type-check script，但 build 自带 vue-tsc，另执行 vue-tsc --noEmit。
- 没有标准 pytest 套件；不能用 70 个专项脚本数量替代单元/服务/API 分层覆盖。
- 现有 8 个浏览器脚本本轮未运行；LoongArch 测试缺失。

## 15. LoongArch / Kylin Static Compatibility

- 总结：high_risk，不是实机通过。
- Python 风险：pydantic-core、greenlet、httptools、uvloop、watchfiles、lxml、libpq。
- 前端风险：Vite 8/Rolldown lock 含平台二进制；建议预构建静态文件。
- OCR/local model：Tesseract/language pack、llama.cpp/GGUF 必须目标机单独验证。
- 部署风险：缺 .service/.conf，文件权限、SELinux/麒麟策略未知。

## 16. Dead Code and Duplicate Code Candidates

- dead candidates：24；duplicate candidates：42；deprecated candidates：45。
- candidate：frontend 未引用 API/asset、历史 legacy/docs.zip、旧端口脚本、重复 repository CRUD/route response helper。
- evidence：AST body hash、全局引用、router/menu/import、Git tracked/untracked、端口文本匹配。
- confidence：仅 exact duplicate/high-confidence AST 可标 high；动态 adapter/router/model/frontend route 一律保守。
- risk：静态扫描会漏字符串注册、__init__ metadata、动态 import 和兼容路由。
- recommended action：Task 25H 逐项人工复核；本任务不处理候选，不触碰 migration。

## 17. Enterprise Capability Gap

| capability | status | gap |
|---|---|---|
| 高可用 | missing | 单实例、进程内限流、无 HA 演练 |
| 备份恢复 | missing/P0 | 无正式脚本与恢复演练 |
| 可观测性 | partial | status/log/trace 有；metrics/alert/tracing 无 |
| 配置治理 | partial | pydantic settings/production guard 有；外部 secret store 无 |
| 数据生命周期 | partial | archive 有；日志/媒体/候选保留策略无 |
| 审计 | B | 专项审计表多；通用 operation_logs 未覆盖 |
| 安全 | B | 基础门禁较好；token 撤销、secret rotation、多实例限流不足 |
| 性能 | partial | 小样本可用；全表聚合和目标机容量未知 |
| 可维护性 | partial | 分层好；重复/旧端口/候选多、无标准测试体系 |
| 可扩展性 | B | adapter/agent registry 可扩展；真实 provider/索引生命周期未闭环 |

## 18. Competition Demonstration Readiness

- 可展示：登录/RBAC、文档/切片/审核、真实关键词 references、诊断、SOP、任务、记录、KG、人工修正、Agent 审批/转换。
- 有条件展示：历史 Cloud/MIMO/OCR real-call 只能展示持久化记录和审计证据，本轮不代表实时在线。
- 不应宣称：真实 DashVector/Embedding、共享图文向量、相似图片检索、LoongArch/Kylin 实机、企业级 HA。
- 当前演示就绪度：中。Windows 本地可复现，但零分硬门与核心检索竞争力未关闭。

## 19. P0 / P1 / P2 Issues

### P0

1. LoongArch/Kylin 未实机验收，且缺 systemd/Nginx 产物；影响：零分风险；任务：25G。
2. 真实 Embedding/DashVector/跨模态匹配缺失；影响：核心赛题要求不满足；任务：25B。
3. 无检索/视觉准确率金标准；影响：无法证明精准语义检索和识别有效；任务：25B。
4. 生产密钥/管理员密码治理未闭环、历史密钥需轮换；影响：安全事故；任务：25E/25G。
5. 无备份恢复；影响：数据不可恢复；任务：25E/25G。
6. SOP 显式中止/禁止/前置 gate 不完整；影响：电气作业安全；任务：25D。

### P1

1. Record center 全量聚合/内存分页；影响：数据增长后延迟和内存；任务：25E。
2. correction accepted 不回流；影响：持续学习闭环不成立；任务：25C。
3. 无真实 rerank/citation faithfulness；影响：检索竞争力和可信性；任务：25B。
4. KG 候选积压、版本/冲突/质量分不足；影响：知识污染；任务：25C。
5. 缺标准 pytest、当前浏览器与长期稳定性验收；影响：回归风险；任务：25E/25F。
6. 工作树高度 dirty；影响：交付混入历史/构建产物；任务：25H。

### P2

1. README 有泛新能源/储能旧表述和旧端口；任务：25H。
2. 重复函数/未引用文件/legacy 候选需复核；任务：25H。
3. UI 技术术语密集、无当前视觉/无障碍走查；任务：25F。
4. 缺 ruff/mypy/lint script；任务：25H。
5. 日志/媒体/候选数据保留策略不足；任务：25E。

## 20. Keep / Enhance / Refactor / Remove Candidate Matrix

| module | decision | rationale |
|---|---|---|
| FastAPI/Vue/PostgreSQL/Alembic | KEEP | 主架构与真实持久化已验证 |
| JWT/RBAC/上传安全/脱敏 | ENHANCE | 基础好，补 token/secret/多实例限流 |
| 文档解析/切分 | LOCAL_REFACTOR | 增加结构保真和质量门 |
| 关键词检索/references | KEEP + ENHANCE | 当前可信主线 |
| Embedding/DashVector/hybrid/rerank | MAJOR_REFACTOR | 当前 D 级 |
| 多模态/跨模态 | MAJOR_REFACTOR | OCR/视觉 B，跨模态 C/E |
| KG/贡献 | ENHANCE | 已参与业务，补质量/版本/冲突 |
| correction feedback | MAJOR_REFACTOR | 记录有、回用无 |
| SOP/task | LOCAL_REFACTOR | 补结构化安全 gate |
| record center | MAJOR_REFACTOR | 全量聚合性能风险 |
| Agent approval/conversion | KEEP | 人工边界和并发防重已验证 |
| legacy/重复/未引用候选 | REMOVE_CANDIDATE | 仅候选，Task 25H 复核后决定 |
| 目标机部署产物 | REPLACE/ADD | 当前只有文档/脚本路线，需正式产物 |

## 21. Final Judgment

**选择 C：关键主链路重构。**

依据：35 项已 verified，说明主架构和业务底座值得保留；但 3 项 placeholder/mock 与 5 项 missing 集中在真实向量、跨模态、评估、反馈回用、备份恢复等赛题/企业硬点，无法靠零散修补达标。后续按 25B -> 25C/25D -> 25E -> 25F -> 25G -> 25H 推进。

## Audit Scope Appendix

- files inventoried：968
- backend production files：189
- frontend production files：102
- scripts/check files：81
- docs：62
- migrations：8
- untracked files in scope：61
- generated assets：120
- code files / lines（含历史交付和构建产物分类）：796 / 111360
- storage policy：目录与数量盘点，未读取用户内容。

<!-- TASK25A_R1_CORRECTION_START -->

## Task 25A-R1 更正：证据驱动重基线

R1 于 2026-07-10T13:51:23.944120+00:00 重建证据模型。原 83 项 maturity 是历史审计观察，不再作为当前最终结论。
新统计：VERIFIED=24，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED=36，PARTIAL=16，PLACEHOLDER_OR_MOCK=4，MISSING=3。
新结论以 `.runtime/task25a_r1/evidence_registry.json`、`test_execution_registry.json` 和自动规则为准；历史 real-call、mock、browser、性能和 LoongArch 实机证据不再混写。
52 个 deleted 已逐项分类：生成资产=52，疑似误删=0。

<!-- TASK25A_R1_CORRECTION_END -->
