# Task 25A-R1 性能轻量基线报告

生成时间：2026-07-10T16:32:55.235023+00:00

## 方法修正

- 账号与密码只从环境或任务私有安全测试配置加载，脚本没有默认用户名/密码，也不输出密码。
- QPS=实际完成请求数/真实批次墙钟时间；serial 与 concurrency 分开，warmup、并发错误、超时和业务断言失败均进入统计。本地负载使用不同 127.25.x.y 源地址模拟独立客户端，未修改或关闭按客户端限流。
- 读取型参数为 5+100+100/workers=10；写入型参数为 2+20+20/workers=5。写入仅使用 `Task25AR1_` 标记、规则模式且禁用真实 provider。

## Endpoint 结果

| Endpoint | Profile | Serial p50/p95/p99 ms | Concurrent p50/p95/p99 ms | QPS | 失败/超时 | 分类 |
|---|---|---|---|---:|---|---|
| `GET /api/health` | read | 15.758 / 31.639 / 32.303 | 16.522 / 31.198 / 41.304 | 531.518 | 0 / 0 | PASS |
| `POST /api/auth/login` | write | 112.512 / 144.795 / 151.823 | 134.439 / 153.865 / 158.577 | 35.774 | 0 / 0 | PASS |
| `GET /api/devices?page=1&page_size=20` | read | 29.332 / 40.265 / 47.53 | 47.786 / 1393.553 / 1674.515 | 49.16 | 0 / 0 | NEEDS_OPTIMIZATION |
| `GET /api/knowledge/documents?page=1&page_size=20` | read | 30.544 / 44.286 / 50.372 | 45.919 / 132.516 / 281.698 | 147.215 | 0 / 0 | PASS |
| `GET /api/kg/search?keyword=SUN2000&limit=20` | read | 31.245 / 54.712 / 61.619 | 93.338 / 284.58 / 310.669 | 84.59 | 0 / 0 | PASS |
| `POST /api/retrieval/query` | write | 65.551 / 97.64 / 112.718 | 91.505 / 95.695 / 95.698 | 54.553 | 0 / 0 | PASS |
| `POST /api/diagnosis/analyze` | write | 95.5 / 196.05 / 212.575 | 121.884 / 258.035 / 303.591 | 30.696 | 0 / 0 | PASS |
| `GET /api/sop/templates?page=1&page_size=20` | read | 31.595 / 49.129 / 57.411 | 60.85 / 154.4 / 265.05 | 127.66 | 0 / 0 | PASS |
| `GET /api/maintenance/tasks?page=1&page_size=20` | read | 36.266 / 70.653 / 93.778 | 162.172 / 269.647 / 397.156 | 52.475 | 0 / 0 | PASS |
| `GET /api/record-center/search?record_type=all&page=1&page_size=20` | read | 783.701 / 1211.576 / 1383.718 | 11108.307 / 12132.309 / 12244.095 | 0.895 | 0 / 0 | NEEDS_OPTIMIZATION |
| `GET /api/kg/business-context?manufacturer=huawei&product_series=SUN2000&question=low%20insulation&limit=20` | read | 131.661 / 232.744 / 298.743 | 1476.788 / 2029.25 / 2114.376 | 6.559 | 0 / 0 | NEEDS_OPTIMIZATION |
| `GET /api/agents/runs?page=1&page_size=20` | read | 29.15 / 42.609 / 52.23 | 50.545 / 159.646 / 291.67 | 125.639 | 0 / 0 | PASS |
| `GET /api/system/status` | read | 30.519 / 46.076 / 49.049 | 37.714 / 191.586 / 260.375 | 174.56 | 0 / 0 | PASS |

## 汇总

- endpoints=13；samples=2176；error_rate=0.0000%；timeout_rate=0.0000%。
- threshold result: **NEEDS_OPTIMIZATION**。阈值只用于审计分类，未为了通过修改业务或降低安全控制。
- Record Center serial p50/p95/p99=783.701/1211.576/1383.718 ms。

## 资源证据

- before RSS=121905152；after RSS=352002048。
- database connections before=11；after=11。
- 无法可靠采集的 peak/CPU/threads 字段明确标记 unavailable，没有伪造。

## Record Center

专项静态与运行时审计见 `.runtime/task25a_r1/record_center_query_audit.json`；Task 25E 建议将异构记录过滤、排序和分页下推到 SQL，并用生产规模夹具执行 EXPLAIN ANALYZE。
