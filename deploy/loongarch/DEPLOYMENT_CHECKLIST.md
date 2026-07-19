# 部署检查清单

- [ ] 主机架构由 `uname -m` 返回 `loongarch64`
- [ ] `/etc/os-release` 明确识别为银河麒麟/Kylin
- [ ] Python >= 3.10，来自目标机原生仓库或受控构建
- [ ] PostgreSQL、Nginx、systemd 已由系统包管理器离线安装
- [ ] gcc/g++/make/pkg-config/Rust/Cargo/pg_config 可用
- [ ] libpq、OpenSSL、libffi、libjpeg、libpng、zlib 开发库可用
- [ ] wheelhouse 只含 `py3-none-any` 或 `loongarch64` wheel
- [ ] requirements 与 wheelhouse SHA-256 清单完整匹配
- [ ] `/etc/energy-maintenance/backend.env` 已替换全部 `CHANGE_ME`，权限 0640/0600
- [ ] `TASK25B_ALLOW_FULL_REINDEX=false`，SmartLogger 未加入任何 Pilot 索引操作
- [ ] 前端 dist 已在开发/构建环境完成，生产机无 Node.js/npm/uv 依赖
- [ ] 迁移前备份已完成并可读
- [ ] Alembic heads/current 均为 `20260712_0015`
- [ ] `current` 使用原子软链接切换，至少保留一个旧 release
- [ ] systemd 与 Nginx 配置测试通过
- [ ] `/api/health` 与 `/api/system/deployment-readiness` 返回统一响应结构
- [ ] 尚未执行的真实机项目保持 PENDING，不伪造 PASS

