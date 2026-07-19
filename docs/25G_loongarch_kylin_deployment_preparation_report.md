# Task 25G：LoongArch + 银河麒麟无 Docker 部署准备报告

最终状态：`TASK25G_LOONGARCH_PREPARATION_PASS_REAL_MACHINE_PENDING`

本报告只证明 Windows/amd64 上的源码、模板、依赖分类、离线策略、dry-run 和应用回归准备完成。它不证明 LoongArch 二进制兼容、银河麒麟安装、原生扩展构建、真实机性能或最终离线包可用。

## 1. 当前项目基线

Task 25D/25E/25F-R1 冻结报告与 runtime 哈希保持不变；Alembic heads/current 为 `20260712_0015`。冻结脚本首次数据库计数使用了不存在的 `approval_status` 字段，因此不可变 snapshot 将该探针诚实记录为 `UNAVAILABLE/ProgrammingError`；脚本源已修正为 `review_status`，没有覆盖冻结文件。随后通过只读回归前后对账恢复基线：文档 372、已批准文档 122、expert_verified 1，三项均未变化。当前 1 条 expert_verified 记录创建于 2026-07-11、审核于 2026-07-14，早于 Task 25G 冻结；本任务按边界未修改或删除它。四个冻结向量 Partition 计数为 `{"pilot_r2": 1262, "pilot_r3_semantic": 416, "pilot_r4_grounded": 1289, "pilot_r5_query_aware": 2508}`。

## 2. Task 25F-R1 状态

保持 `TASK25F_R1_COMPATIBILITY_PASS`。本任务只读校验旧报告和 runtime 聚合哈希，没有执行会覆盖旧 evidence 的历史 writer。

## 3. Task 25C 边界

仍为 `MULTIMODAL_BENCHMARK_INSUFFICIENT`；未扩充 Benchmark、未调用真实 OCR/视觉 Provider、未把不足状态包装成通过。

## 4. R6 边界

仍为 `DEFERRED_QWEN3_RERANK_CONFIG`；未恢复 Qwen3、未变更 RAG 权重或 nDCG 结论。

## 5. LoongArch 部署架构

采用 `/opt/energy-maintenance/releases/<release-id>`、`current` 原子软链接、`shared/venv`、独立数据/日志/配置目录，前端由 Nginx 托管，后端仅监听 `127.0.0.1:8012`。

## 6. 无 Docker 方案

生产路线仅含 Python venv、PostgreSQL、systemd 与 Nginx；`docker_required=false`，未创建 Dockerfile、Compose、Kubernetes 或容器交付物。

## 7. Runtime Windows-only 审计

扫描生产 `backend/app`、`frontend/dist` 和 `deploy/loongarch`：阻断项 0，硬编码盘符、Windows subprocess/import 均为 0。

## 8. Linux 路径治理

上传、processed-media、tmp、日志、环境文件均位于可配置的 POSIX 绝对路径；上传与日志不在源码或前端静态目录。环境文件建议 0600/0640。

## 9. Python 依赖分类

生产 requirements 共 28 个固定版本条目；审计清单覆盖 42 个关键依赖，Native 分类覆盖率 1.0，UNKNOWN=0。

## 10. Native 依赖风险

- `pydantic-core`: REAL_MACHINE_BUILD_REQUIRED — Rust native extension required by Pydantic v2.
- `Pillow`: SYSTEM_LIBRARY_REQUIRED — Image codecs and C extension require target libraries.
- `lxml`: SYSTEM_LIBRARY_REQUIRED — python-docx uses libxml2/libxslt-backed lxml.
- `MarkupSafe`: REAL_MACHINE_BUILD_REQUIRED — Optional C speedups may lack a LoongArch wheel.
- `psycopg`: SYSTEM_LIBRARY_REQUIRED — Pure Python package dynamically links the system libpq.

## 11. psycopg/libpq 策略

生产依赖使用 `psycopg==3.3.4` 纯 Python 包配合系统 libpq；`psycopg-binary` 只允许作为 Windows 开发 optional extra，不进入 LoongArch requirements。备份脚本通过环境传递凭据，不把密码放在 pg_dump 命令行。

## 12. pydantic-core 风险

`pydantic-core==2.46.4` 是 Rust Native 关键风险，必须在真实 loongarch64 构建机通过 Rust/maturin 构建并完成 import/schema probe；本机只记录 amd64 基线。

## 13. Pillow 风险

`Pillow==12.3.0` 依赖 libjpeg/libpng/zlib 等系统库，必须目标机构建并验证图像/PDF 处理路径。

## 14. cryptography/cffi 风险

两者当前不在生产锁定依赖。若未来引入，必须显式准备 OpenSSL、libffi、Rust/C 工具链并在真实机验证，不能自动视为兼容。

## 15. Uvicorn 纯 Python 策略

systemd 使用 `venv/bin/python -m uvicorn`、标准 asyncio+h11 路径；不强制 uvloop、httptools、orjson，禁用 reload，workers 可配置。

## 16. LoongArch requirements

`requirements-loongarch.txt` 与当前 uv.lock 固定版本对齐；生产清单排除 pytest、Playwright、前端工具链、Windows-only 包和 Uvicorn standard extras。

## 17. 离线 Wheelhouse 规范

Task 25G 未生成 wheelhouse。真实 loongarch64 构建机必须仅产出 `py3-none-any` 或 loongarch64 wheel，拒绝 win_amd64、x86_64、aarch64，并在安装前填充 SHA-256 清单。

## 18. 前端静态部署

前端在构建机生成 dist，生产机只复制静态文件，不需要 Node/npm/uv。相对 API 前缀为 `/api`，dist 共 62 个文件、718723 bytes。

## 19. Nginx

模板提供 SPA fallback、`/api/` 到 `127.0.0.1:8012` 的代理、安全头、缓存策略、上传大小限制及 `autoindex off`；真实机安装前必须执行 `nginx -t`。

## 20. systemd

专用非 root 用户运行，配置来自 `/etc/energy-maintenance/backend.env`，启用 restart-on-failure、权限隔离和 writable path 白名单。

## 21. 生产环境模板

只含 `CHANGE_ME` 占位符和安全默认开关；未读取或输出 backend/.env 内容，模板中 `EXTERNAL_REAL_CALLS_ENABLED=false`、`TASK25B_ALLOW_FULL_REINDEX=false`。

## 22. PostgreSQL/Migration

使用系统 libpq 与 psycopg；迁移前强制备份，只执行 `alembic upgrade head`，目标 revision `20260712_0015`，没有自动 downgrade。

## 23. 原子发布

新 release 先独立安装，`current` 通过临时链接加 `mv -Tf` 原子切换；安装脚本不会自行切换 current，并保留旧版本。

## 24. 备份

升级前创建 PostgreSQL custom-format dump 和 current release 记录；凭据不写命令行、不打印日志。

## 25. 回滚

回滚只切换到已保留 release 并重启后端/重载 Nginx；数据库 downgrade 明确禁止，共享 venv 兼容性需人工确认。

## 26. 健康检查

检查统一 `/api/health` 契约、systemd、Nginx、current、前端入口、目录可写、磁盘、PID、RSS、文件描述符与重启次数，不输出密钥。

## 27. 日志

提供 logrotate、systemd journal 诊断与脱敏收集脚本；日志目录独立于源码，诊断输出会遮蔽 URL 凭据和敏感变量。

## 28. 4核8GB资源基线

建议 2 workers，每 worker DB pool 5 + overflow 1，总应用连接预算 12、含运维余量不超过 14。Windows/amd64 回归后 RSS 观测为 189.19 MiB；这不是 LoongArch 性能验收。

## 29. Dry-run

静态发布/回滚 dry-run 为 PASS；本机 ShellCheck 不可用，已明确记录 `UNAVAILABLE`。WSL bash 命令入口存在但没有 Linux/bash 运行时，因此没有伪报 bash -n 或 LoongArch 通过。

## 30. 静态测试

Task 25G 定向测试 24/24 通过；Shell、模板、离线、依赖、import、路径、前端和安全审计均为 PASS。

## 31. 完整回归

完整 pytest：455 passed、3 skipped；compileall、Alembic、安全、RBAC、RAG、Agent、转换、前端 build/vue-tsc、Task 25D/E/F-R1 冻结完整性均为 PASS。

## 32. Final Smoke

8012 已确认运行当前项目代码，final smoke 为 PASS、failed=0。浏览器控制组件因本地初始化冲突未能进行视觉断言；API 集成测试、前端构建和 final smoke 已通过，但不把视觉审核伪报为 PASS。

## 33. 真实机器验收状态

`real_machine_acceptance=PENDING`。没有执行 `check_task25g_loongarch_real_machine.py --allow-real-machine-acceptance`；Windows/amd64 禁止输出真实机 PASS。

## 34. 向量未修改

pilot_r2/r3/r4/r5 和默认 Partition 未写入；Embedding writes=0，DashVector writes=0，正式全量重建=false。

## 35. expert_verified=false

本节的 `false` 表示 Task 25G 未执行 expert_verified 写入。数据库当前存在 1 条早于 Task 25G 的 expert_verified 记录，回归前后均为 1；Task 25G 写入数为 0，也未修改批准数。由于任务禁止专家审核变更，该既有记录被保留并单独记录为边界事实。

## 36. 正式全量重建未执行

`TASK25B_ALLOW_FULL_REINDEX` 在回归和生产模板中均为 false；未执行 Pilot/SmartLogger 索引或全量重建。

## 37. 未打包

未生成 ZIP、tar.gz、wheelhouse 或最终安装包；现有 ZIP inventory 与冻结基线一致，delivery/delivery_staging 未更新。

## 38. 未提交 Git

未执行 git add/commit/reset/clean/restore；staged 文件数为 0。

## 下一步

在真实 LoongArch64 + 银河麒麟 V10/V11 构建/目标机上：准备系统 RPM 和 Native 工具链，构建并校验 wheelhouse，按部署清单安装，在 4核8GB 下完成长期稳定性、重启恢复、备份恢复和回滚验收。Task 25C 与 R6 保持各自现有边界，不在 Task 25G 内恢复。
