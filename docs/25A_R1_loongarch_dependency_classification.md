# Task 25A-R1 LoongArch / Kylin 依赖用途分类

生成时间：2026-07-10T13:39:04.196977+00:00

## 结论

- 本轮只完成 Windows 静态依赖分类；LoongArch/Kylin 实机状态为 **NOT_EXECUTED**，不得表述为通过。
- 前端可在非龙芯构建机预构建并只把静态文件部署到目标服务器；Node.js、Vite/Rolldown 的 build-time 风险不等于服务器 runtime 阻断。
- Playwright/Chromium 是测试依赖；uvloop、httptools、watchfiles 可禁用或不进入正式服务。
- pydantic-core、greenlet、psycopg/libpq 是 Task 25G0 的最高优先级探针。

## 用途统计

- BUILD_TIME_ONLY: 3
- DEVELOPMENT_ONLY: 1
- RUNTIME_OPTIONAL: 6
- RUNTIME_REQUIRED: 6
- TEST_ONLY: 2

## 依赖明细

| 依赖 | 版本 | 阶段 | 目标必需 | Native | 风险 |
|---|---|---|---|---|---|
| pydantic-core | 2.46.4 | RUNTIME_REQUIRED | true | true | HIGH |
| greenlet | 3.5.1 | RUNTIME_REQUIRED | true | true | HIGH |
| psycopg | 3.3.4 | RUNTIME_REQUIRED | true | false | HIGH |
| libpq | system_or_not_locked | RUNTIME_REQUIRED | true | true | HIGH |
| httptools | 0.8.0 | RUNTIME_OPTIONAL | false | true | MEDIUM |
| uvloop | 0.22.1 | RUNTIME_OPTIONAL | false | true | MEDIUM |
| watchfiles | 1.2.0 | DEVELOPMENT_ONLY | false | true | LOW |
| lxml | 6.1.1 | RUNTIME_OPTIONAL | false | true | MEDIUM |
| Pillow | system_or_not_locked | RUNTIME_OPTIONAL | false | true | MEDIUM |
| Tesseract | system_or_not_locked | RUNTIME_OPTIONAL | false | true | MEDIUM |
| Node.js | system_or_not_locked | BUILD_TIME_ONLY | false | true | LOW |
| Vite | 8.0.16 | BUILD_TIME_ONLY | false | false | LOW |
| Rolldown native binding | system_or_not_locked | BUILD_TIME_ONLY | false | true | MEDIUM |
| Playwright | system_or_not_locked | TEST_ONLY | false | false | LOW |
| Chromium | system_or_not_locked | TEST_ONLY | false | true | LOW |
| pypdf | 6.12.2 | RUNTIME_REQUIRED | true | false | LOW |
| python-docx | 1.2.0 | RUNTIME_REQUIRED | true | false | MEDIUM |
| psycopg-c | system_or_not_locked | RUNTIME_OPTIONAL | false | true | MEDIUM |

## 下一步

Task 25G0 必须在真实 LoongArch + Kylin 机器执行安装、import、PostgreSQL 连接、文档解析和服务启动探针；本报告不能替代实机证据。
