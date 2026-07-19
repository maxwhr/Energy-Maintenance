# 真实 LoongArch + 银河麒麟验收清单

只有在真实 `loongarch64` 银河麒麟机器上，并经操作者显式授权后，才可填写本表。

- [ ] 平台：`loongarch64`
- [ ] OS：银河麒麟，版本与内核已记录
- [ ] Python 原生运行，无 qemu/跨架构伪装
- [ ] 所有生产依赖导入成功
- [ ] pydantic-core、Pillow、lxml、cryptography/cffi（若安装）来源与构建日志可追溯
- [ ] psycopg 使用系统 libpq；未安装 psycopg-binary
- [ ] 未安装/未强制 uvloop、httptools、orjson、watchfiles
- [ ] Alembic current 为 `20260712_0015`
- [ ] systemd 以专用非 root 用户运行并启用 hardening
- [ ] Nginx `/api/` 反向代理和 SPA fallback 正常
- [ ] 上传、处理媒体、临时文件和日志权限符合模板
- [ ] `/api/health`、登录、文档列表、检索（不触发真实外部 API）通过
- [ ] deployment-readiness API 不泄露绝对路径、环境值、密钥或数据库凭据
- [ ] 2 workers 下 30 分钟稳态 RSS、CPU、错误率已记录
- [ ] 数据库连接总量 <= 14
- [ ] 备份恢复演练已在隔离数据库验证
- [ ] release 软链接回滚成功，未执行数据库 downgrade
- [ ] 外部 Embedding/DashVector 调用为 0，full reindex 为 false

完成证据应写入独立验收记录。Windows 生成的 Task 25G 报告只能保持 `REAL_MACHINE_PENDING`。

