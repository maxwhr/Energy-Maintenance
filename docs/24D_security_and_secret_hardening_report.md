# Task 24D 安全与密钥审计及生产级安全加固报告

## 1. 任务范围

本任务围绕 Energy-Maintenance 的交付前安全加固展开，重点覆盖生产启动配置校验、CORS 治理、请求体大小限制、轻量限流、日志脱敏、密钥扫描、上传安全和 RBAC 矩阵验收。

本任务未执行打包、未提交 Git、未新增 Alembic migration、未调用真实 DashVector / Embedding / MIMO / OCR / Cloud LLM API，且未修改本机 `backend/.env` 中的真实配置值。

## 2. 安全加固总览

- 生产启动校验：新增 `backend/app/core/security_config.py`，在 FastAPI startup 阶段执行生产强校验。
- CORS：后端 CORS 来源、方法、请求头从 settings 读取，生产环境禁止通配来源。
- 请求体限制：新增 `RequestSizeLimitMiddleware`，普通 JSON 请求与上传请求使用不同大小限制。
- rate limit：新增内存级 `InMemoryRateLimitMiddleware`，用于本地和单实例基础限流。
- 日志脱敏：增强 `ExternalApiSanitizer`，覆盖 API Key、Authorization、token、password、base64 图片、本地路径。
- secret scan：新增 `check_secret_leak_scan.py`，扫描文档、脚本、前后端代码并输出脱敏 JSON。
- upload security：新增 `check_upload_security.py`，覆盖扩展名、路径遍历、绝对路径、请求体限制、viewer 写入阻断和预览鉴权。
- RBAC matrix：新增 `check_rbac_security_matrix.py`，覆盖 admin / expert / engineer / viewer / anonymous 关键模块权限。
- system status：`/api/system/status` 增加脱敏安全状态字段，只展示 configured / enabled / blocked，不返回密钥值。
- 外部真实调用边界：新增 `EXTERNAL_REAL_CALLS_ENABLED=false` 默认开关，Key 已配置不等于允许真实外部调用。

## 3. 密钥风险处理

用户曾在对话中泄露过真实 DashVector / 模型相关 Key，后续真实使用前必须在对应平台执行轮换。本任务不会在文档、终端或运行时响应中输出任何 Key 原文。

`backend/.env` 未被覆盖；`backend/.env.example` 仅保留占位或空值。密钥扫描脚本允许本机 `.env` 出现已配置状态，并以 `passed_with_notes` 记录，不输出值。

## 4. 生产配置校验

生产模式 `APP_ENV=production` 下会校验：

- `SECRET_KEY` 必须配置、非占位且满足最小长度。
- `ADMIN_PASSWORD` 必须显式配置，不能使用弱口令。
- `DATABASE_URL` 必须使用 PostgreSQL，禁止 SQLite。
- `CORS_ALLOWED_ORIGINS` 禁止 `*`。
- 上传目录和日志目录必须可写。
- enabled=true 的真实外部 provider 必须具备必要配置，否则保持 blocked / unavailable，不能进入真实调用。

开发环境只在系统状态中显示 warning，不阻断本地验收。

## 5. API 与日志脱敏

脱敏覆盖范围包括 External API Provider Gateway、Model Gateway、DashVector / Embedding、MIMO / OCR / Cloud LLM 请求摘要、agent logs、model/vector 调用日志以及异常消息。

禁止保存或返回：

- API Key / Authorization / token / password / secret
- 完整 base64 图片
- 本地绝对路径
- 外部调用完整 headers

## 6. RBAC 审计

RBAC 矩阵脚本覆盖：

- anonymous：只允许健康检查和必要公开状态。
- viewer：只读访问，禁止上传、诊断、SOP、任务创建、外部 API dry-run、Agent 执行和审核。
- engineer：允许一线业务创建与执行，禁止用户管理、审核、审批、草稿转换、向量重建等高风险操作。
- expert：允许审核/审批/转换类专家操作，禁止用户管理。
- admin：保留系统管理能力。

## 7. 上传安全

验收覆盖：

- 正常 txt 文档上传通过。
- 超大 JSON 请求返回 413。
- 不允许扩展名被拒绝。
- `../` 和绝对路径文件名被净化或拒绝。
- viewer 上传知识文档和媒体被拒绝。
- 媒体预览按只读权限可访问或按接口设计阻断，不返回本地绝对路径。

## 8. 回归测试

已执行并通过：

- `uv run python -m compileall app scripts`
- `uv run python -m alembic -c alembic.ini heads`
- `uv run python -m alembic -c alembic.ini current`
- `check_security_config_status.py`
- `check_secret_leak_scan.py`
- `check_log_sanitization.py`
- `check_upload_security.py`
- `check_rbac_security_matrix.py`
- DashVector Hybrid RAG dry-run 回归
- Agent artifact / curator / diagnosis-SOP-task / multimodal evidence / external API gateway 回归
- `npm.cmd install`
- `npm.cmd audit`
- `npm.cmd run build`
- `backend/scripts/build_and_install_frontend.ps1`
- `scripts/final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`

实际 Alembic heads/current 为 `20260601_0008 (head)`。Task 24D 未新增 migration、未执行 `alembic upgrade head`。

## 9. Remaining Risks

- 已泄露过的真实 Key 必须轮换后才可用于生产或真实 online 验收。
- 当前工作树仍有大量历史任务未提交文件，本任务未清理。
- LoongArch / Kylin 尚未实机部署验收。
- DashVector、MIMO、OCR、Cloud LLM 等真实 API real-call 未在本任务执行。
- 生产部署仍需 HTTPS、Nginx/systemd、备份、日志轮转和网关级限流。
- Windows PostgreSQL 当前仍使用本地 standalone 55432 验证方式。

## 10. No-package Confirmation

Task 24D 禁止打包。本任务未执行 `Compress-Archive`，未生成新的 delivery zip，未更新 `delivery/` 内既有交付包。当前 `delivery/` 与 `delivery_staging/` 为历史遗留目录/文件，不是本轮创建。

## 11. Git 状态

本任务不执行 `git add`、不执行 `git commit`、不清理历史未提交文件。最终状态以 `git status --short` 为准。

## Task 24E Follow-up

Task 24E keeps the Task 24D security boundary: conversion logs and history expose trace ids, status, target ids, sanitized errors, and metadata summaries only. They must not expose API keys, Authorization headers, raw tokens, base64 media, or local absolute paths. The conversion void endpoint remains reserved and does not delete formal data.
