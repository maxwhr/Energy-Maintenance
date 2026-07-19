# LoongArch + 银河麒麟原生部署准备

本目录是 Task 25G 的源码级部署材料，不是交付包，也不包含 wheelhouse。正式路线为 LoongArch64 + 银河麒麟 + Python venv + PostgreSQL + systemd + Nginx，全程不要求 Docker、Node.js、npm 或 uv 出现在生产机。

## 边界

- Windows/amd64 仅执行静态审计、dry-run 和现有应用回归，不能签发真实机通过结论。
- 离线 wheelhouse 必须在受控的真实 `loongarch64` 构建环境创建并校验，禁止复用 x86_64、aarch64、Windows wheel。
- 数据库仅允许 `alembic upgrade head`；回滚脚本只原子切换 `current` 软链接，绝不自动 downgrade。
- 配置文件只提供占位模板，严禁把 `backend/.env` 或真实凭据复制进发布材料。

## 推荐执行顺序

1. 在目标机离线导入系统 RPM、Python sdist/wheel、预构建前端 dist 和本目录。
2. 人工核对 `DEPLOYMENT_CHECKLIST.md`，执行 `scripts/preflight.sh`。
3. 执行 `initialize_directories.sh`，人工创建 `/etc/energy-maintenance/backend.env` 并设为 `0640`。
4. 在目标 loongarch64 构建机生成 wheelhouse；执行 `verify_offline_assets.sh` 与 SHA-256 校验。
5. 分别执行 `install_backend.sh`、`install_frontend.sh`，此时不切换 `current`。
6. 执行备份和 `migrate_database.sh`，确认 revision 为 `20260712_0015`。
7. 原子创建或切换 `current`，再配置 systemd 与 Nginx。
8. 启动服务，完成 `REAL_MACHINE_ACCEPTANCE_CHECKLIST.md`，最后以显式授权运行真实机验收脚本。

所有变更型 shell 脚本支持 `--dry-run`。环境目录可通过 `EM_ROOT`、`EM_DATA_DIR`、`EM_LOG_DIR`、`EM_CONFIG_FILE` 等变量覆盖。

