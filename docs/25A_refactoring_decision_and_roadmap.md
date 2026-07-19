# Task 25A 重构决策与路线图

## 1. 主方案

**选择 C：关键主链路重构。**

不建议整体重写。现有 FastAPI/Vue/PostgreSQL 分层、JWT/RBAC、知识文档、任务、记录、KG、Agent 审批/转换和审计表具有保留价值；需要重构的是决定赛题竞争力的真实多模态识别、语义/跨模态检索、SOP 安全 gate、性能和目标机部署主链路。

## 2. Keep / Enhance / Refactor

- KEEP：FastAPI + Vue B/S、PostgreSQL/Alembic、统一 /api、JWT/RBAC、上传安全、任务状态机、Agent 人工审批/转换。
- ENHANCE：知识贡献/KG、记录中心、前端证据展示、审计日志、测试体系。
- MAJOR_REFACTOR：真实 Embedding/DashVector/hybrid/rerank/评估、跨模态匹配、SOP 合规与中止条件。
- REMOVE_CANDIDATE：只记录在 JSON 候选清单；Task 25A 不执行清理。
- REPLACE：只在目标机证明依赖不可安装或真实检索方案不达标时替换具体 adapter，不替换主架构。

## 3. 后续任务

### Task 25B：多模态识别与高精度检索主链路重构

- 目标：真实图文识别、跨模态/语义检索、DashVector/Embedding、rerank、评估集
- 涉及模块：RAG、多模态、media、vector、retrieval、前端证据展示
- 优先级：P0
- 前置条件：轮换 provider 密钥；确定 embedding/图像检索方案；准备标注集
- 验收标准：真实 embedding/DashVector 闭环；跨模态/检索指标达门；引用可解释
- 是否涉及 migration：可能
- 是否涉及真实外部 API：是
- 是否需要 LoongArch：建议后期复测
- 风险：高：外部 API、维度一致性、数据集质量
- 工作量：XL

### Task 25C：知识治理、知识图谱与反馈闭环增强

- 目标：修正回用、语义去重、KG 版本/冲突/质量、候选积压治理
- 涉及模块：correction、contribution、KG、review、index lifecycle
- 优先级：P1
- 前置条件：Task 25B 提供真实 embedding 与质量指标
- 验收标准：accepted correction 可显式转贡献；KG 质量分、版本、冲突和追溯闭环
- 是否涉及 migration：可能
- 是否涉及真实外部 API：否（除非真实 embedding 走外部）
- 是否需要 LoongArch：否
- 风险：中高：历史数据兼容和候选污染
- 工作量：L

### Task 25D：标准化作业和安全合规闭环增强

- 目标：前置/完成/中止条件、禁止项、PPE、合规规则版本、任务验收 gate
- 涉及模块：SOP、execution、task、maintenance record、approval
- 优先级：P0/P1
- 前置条件：收集厂家/现场安全规范并由专家审校
- 验收标准：高风险操作硬阻断；SOP 到任务到记录到知识的证据闭环
- 是否涉及 migration：是
- 是否涉及真实外部 API：否
- 是否需要 LoongArch：否
- 风险：高：安全规则错误会造成现场风险
- 工作量：L

### Task 25E：性能、稳定性、可观测性与压力测试

- 目标：优化 record center、索引/查询、限流、日志保留、指标、备份恢复、长稳
- 涉及模块：repositories、middleware、logs、system、scripts
- 优先级：P0/P1
- 前置条件：固定数据规模和性能 SLO；准备可恢复测试库
- 验收标准：四核 8GB 目标；p95/QPS/error rate 达门；备份恢复成功
- 是否涉及 migration：可能
- 是否涉及真实外部 API：否
- 是否需要 LoongArch：最终需
- 风险：中高：压测污染数据或误伤服务
- 工作量：L

### Task 25F：比赛演示场景、前端交互和测试数据完善

- 目标：真实场景、技术状态降噪、浏览器点击、截图基线、失败态和证据叙事
- 涉及模块：frontend、demo data、browser scripts、docs
- 优先级：P1/P2
- 前置条件：25B-25E 主链路冻结；准备可公开样例
- 验收标准：关键路径浏览器通过；无 mock 冒充；演示可在限定时间复现
- 是否涉及 migration：否
- 是否涉及真实外部 API：否
- 是否需要 LoongArch：否
- 风险：中：演示数据与真实能力边界混淆
- 工作量：M

### Task 25G：LoongArch / 银河麒麟实机部署验收

- 目标：依赖构建、PostgreSQL、systemd、Nginx、权限、安全策略、性能、备份
- 涉及模块：deploy、shell、backend/frontend static、database
- 优先级：P0
- 前置条件：真实 LoongArch + Kylin V10/V11 机器；25B-25F 冻结
- 验收标准：实机完整闭环与重启恢复；保存命令、版本、日志和性能证据
- 是否涉及 migration：否（只执行既有 migration）
- 是否涉及真实外部 API：可选，除非比赛路线依赖云 provider
- 是否需要 LoongArch：是
- 风险：极高：零分硬门、native wheel 与系统库
- 工作量：XL

### Task 25H：无用代码清理、变更分组和交付冻结

- 目标：逐项复核 dead/duplicate/deprecated candidates，范围文案、端口、构建产物与 Git 冻结
- 涉及模块：全仓、docs、static、legacy、scripts
- 优先级：P1/P2
- 前置条件：25B-25G 验收完成；人工确认每个候选
- 验收标准：无误删动态注册/migration；分组变更可审计；最终 no-package/交付策略明确
- 是否涉及 migration：否
- 是否涉及真实外部 API：否
- 是否需要 LoongArch：否
- 风险：中：动态路由/注册误删与脏工作树混入
- 工作量：M

## 4. 执行顺序与停止条件

1. 25B 先补零分/竞争力主链路；真实 embedding/vector 未通过前，不宣称语义或跨模态检索。
2. 25C/25D 在 25B 的索引与证据模型上闭环治理和作业安全。
3. 25E 用固定数据规模验证，不为通过测试关闭安全边界。
4. 25F 只展示已验证能力；mock/dry-run 必须显式标识。
5. 25G 是最终硬门；没有实机日志不得进入“已满足 LoongArch/Kylin”结论。
6. 25H 最后清理候选；每个文件先证据复核，migration 永不作为清理对象。

<!-- TASK25A_R1_CORRECTION_START -->

## Task 25A-R1 更正：可靠重构前基线

R1 于 2026-07-10T13:51:23.944120+00:00 重建证据模型。原 83 项 maturity 是历史审计观察，不再作为当前最终结论。
新统计：VERIFIED=24，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED=36，PARTIAL=16，PLACEHOLDER_OR_MOCK=4，MISSING=3。
新结论以 `.runtime/task25a_r1/evidence_registry.json`、`test_execution_registry.json` 和自动规则为准；历史 real-call、mock、browser、性能和 LoongArch 实机证据不再混写。
Task 25G0=GO；Task 25B=CONDITIONAL-GO。候选删除数=0，先探针后重构。

<!-- TASK25A_R1_CORRECTION_END -->

## Task 25B Decision Update

Decision: **CONDITIONAL-GO remains; quality gate blocks completion**. Connectivity and controlled multimodal paths are real and passed, but retrieval quality/performance needs another dev-only tuning cycle followed by a fresh untouched test split. Full formal reindex remains prohibited until `TASK25B_ALLOW_FULL_REINDEX=true` is explicitly authorized.

<!-- TASK25B_R1_BEGIN -->
## Task 25B-R1 controlled blind acceptance (2026-07-11T02:32:50.109583+00:00)

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- Corpus: 24 documents, 192 active chunks, 48 hard negatives.
- Adaptive blind metrics: R@5=1.000000, R@10=1.000000, MRR=0.981481, nDCG@10=0.986331, warm p95=704.712 ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
<!-- TASK25B_R1_END -->


<!-- TASK25B_R2_BEGIN -->
## Task 25B-R2 正式知识 Pilot 状态

- 状态：`BLOCKED_CONFIG`；正式可用语料只有 6 份文档、11 个 active Chunk，未达到 300。
- 独立 Pilot Collection `energy_kn_te_v4_1024_pilot1` 创建被服务商 2 个 Collection 配额阻断；未删除或复用现有 Collection。
- 已生成 150 条 `draft` 候选；`expert_verified=0`，未冻结或运行 `official_pilot_test_v1`。
- 默认 Collection 与 `keyword` 策略未改变；`TASK25B_ALLOW_FULL_REINDEX=false`，全量重建决策为 NO-GO。
- 本任务未打包、未提交 Git；LoongArch/Kylin 仍未实机验收。
<!-- TASK25B_R2_END -->
