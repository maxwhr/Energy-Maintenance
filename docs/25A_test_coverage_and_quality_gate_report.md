# Task 25A 测试覆盖与质量门禁报告

## 1. 结论

- 专项 check/smoke/browser/运维脚本盘点：71 个。
- 标准 pytest 单元测试体系：**missing**。pyproject 未声明 pytest，仓库无标准 tests/ 单元测试套件。
- 浏览器脚本：8 个，但本轮未执行浏览器点击验收。
- 安全脚本：5 个；本轮安全配置、secret scan、日志脱敏、上传安全、40 项 RBAC 通过/通过附注。
- 真实 provider 脚本：9 个；本轮按约束未调用外部 API，历史 Task 24C 证据不可替代当前在线可用性。
- LoongArch：只有静态脚本，无实机测试。

## 2. 本轮质量门

| gate | result | evidence |
|---|---|---|
| compileall | passed | app 与 scripts 编译通过 |
| Alembic heads/current | passed | 20260601_0008 (head) |
| ruff | missing | pyproject 未配置，不擅自格式化 |
| mypy | missing | pyproject 未配置 |
| security config | passed | development 有 warning；production 弱配置能被拒绝 |
| secret scan | passed_with_notes | 3 个本机 .env configured note，0 blocking；不输出值 |
| log sanitization | passed | 无 raw secret/Authorization/base64/local path |
| upload security | passed | 11 checks |
| RBAC | passed | 40 checks, failed=0 |
| DashVector hybrid flow | passed as mock boundary | fake_in_memory + deterministic_test；非真实向量 |
| external gateway | passed as blocked/dry-run | real_external_calls_enabled=false |
| multimodal evidence | passed as blocked/mock boundary | 本轮未 real-call |
| agent flows | passed | multimodal、diagnosis/SOP/task、curator、conversion、并发防重 |
| npm install/audit | passed | 113 packages，0 vulnerabilities |
| type check/build | passed | vue-tsc --noEmit、vue-tsc -b、Vite build |
| frontend static install | passed | copied 59 files |
| final smoke | passed | 23 total，0 failed；retrieval POST 默认跳过，但性能 probe 已覆盖 |
| browser click | not executed | 现有 8 个脚本未在本轮运行 |
| LoongArch/Kylin | not executed | 无目标机 |

## 3. 核心模块覆盖矩阵（静态盘点）

| module | unit_test | service_test | api_test | browser_test | performance_test | security_test | real_provider_test | loongarch_test |
|---|---|---|---|---|---|---|---|---|
| auth | missing_standard_pytest_suite | script_coverage | partial | missing | missing | script_coverage | missing | missing |
| device | missing_standard_pytest_suite | missing | missing | missing | missing | missing | missing | missing |
| knowledge | missing_standard_pytest_suite | script_coverage | script_coverage | script_coverage | missing | missing | missing | missing |
| retrieval | missing_standard_pytest_suite | script_coverage | script_coverage | missing | missing | missing | script_coverage | missing |
| diagnosis | missing_standard_pytest_suite | script_coverage | script_coverage | script_coverage | missing | missing | missing | missing |
| sop | missing_standard_pytest_suite | script_coverage | script_coverage | script_coverage | missing | missing | missing | missing |
| task | missing_standard_pytest_suite | script_coverage | script_coverage | script_coverage | script_coverage | missing | script_coverage | missing |
| record_center | missing_standard_pytest_suite | missing | missing | missing | missing | missing | missing | missing |
| knowledge_graph | missing_standard_pytest_suite | script_coverage | script_coverage | missing | missing | missing | missing | missing |
| multimodal | missing_standard_pytest_suite | script_coverage | script_coverage | script_coverage | missing | missing | script_coverage | missing |
| agent | missing_standard_pytest_suite | script_coverage | script_coverage | script_coverage | missing | missing | script_coverage | missing |
| external_provider | missing_standard_pytest_suite | script_coverage | script_coverage | missing | missing | missing | script_coverage | missing |
| system | missing_standard_pytest_suite | script_coverage | partial | missing | missing | missing | missing | missing |

## 4. 性能门

- 实际运行参数：warmup=1、serial=4、read concurrency=5。
- 请求：93；error rate=0.0；p50=32.615 ms；p95=1233.407 ms；p99=1763.236 ms。
- 为避免应用每分钟 120 次限流把基准污染为 429，本轮未执行脚本默认的 5/20/5 全组合；因此只能算轻量基线。
- 记录中心全量聚合和内存分页是已确认性能风险。

## 5. 必补门禁

1. pytest 单元/服务/API 分层套件和覆盖率阈值。
2. 真实检索评估集、OCR/视觉标注集和 citation faithfulness。
3. 浏览器关键路径、重复提交、权限、网络失败和证据展示。
4. 并发/长稳/故障恢复/日志增长/备份恢复。
5. LoongArch/Kylin 实机安装、启动、业务闭环和性能。

<!-- TASK25A_R1_CORRECTION_START -->

## Task 25A-R1 更正：浏览器、性能与测试注册表

R1 于 2026-07-10T13:51:23.944120+00:00 重建证据模型。原 83 项 maturity 是历史审计观察，不再作为当前最终结论。
新统计：VERIFIED=24，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED=36，PARTIAL=16，PLACEHOLDER_OR_MOCK=4，MISSING=3。
新结论以 `.runtime/task25a_r1/evidence_registry.json`、`test_execution_registry.json` 和自动规则为准；历史 real-call、mock、browser、性能和 LoongArch 实机证据不再混写。
浏览器 passed=7、failed=0；性能 endpoint=13、overall=NEEDS_OPTIMIZATION。

<!-- TASK25A_R1_CORRECTION_END -->
