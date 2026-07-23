# Energy-Maintenance

[![CI](https://github.com/maxwhr/Energy-Maintenance/actions/workflows/ci.yml/badge.svg)](https://github.com/maxwhr/Energy-Maintenance/actions/workflows/ci.yml)

## 项目简介

Energy-Maintenance 是面向华为和阳光电源光伏逆变器的多模态智能检修作业平台。系统围绕设备运维、知识检索、故障辅助诊断、证据追溯和检修任务协同构建，为现场工程师、专家和管理人员提供可审核、可追溯的作业支持。

## 核心能力

- 用户认证与基于角色的访问控制（RBAC）
- 设备台账、产品系列和告警管理
- 知识文档上传、解析、切片与审核
- RAG 检索问答与真实 Citation
- 故障辅助诊断与安全提示
- OCR / Vision 多模态证据处理和人工确认
- 知识图谱、关系证据与来源追溯
- SOP 模板与检修任务管理
- Record Center、关联记录与设备时间线
- 外部模型服务与智能体运行管理

## 技术架构

- 前端：Vue 3、TypeScript、Vite
- 后端：FastAPI、Pydantic
- 数据访问与迁移：SQLAlchemy、Alembic
- 数据库：PostgreSQL
- 运行与代理：Python venv、systemd、Nginx
- 正式部署目标：LoongArch + 银河麒麟
- 正式部署不使用 Docker

## 项目目录

```text
backend/app              后端业务代码
backend/alembic          数据库迁移
backend/tests            后端自动化测试
backend/static/frontend  后端托管的前端正式构建
frontend/src             前端业务代码
frontend/tests           前端单元测试
deploy/loongarch         LoongArch 与银河麒麟部署资源
.github/workflows        GitHub Actions 工作流
```

## 本地开发环境

- Python 3.11
- PostgreSQL 16
- Node.js 20+
- npm

## PostgreSQL 配置

在 `backend/.env` 中配置正式或本地开发数据库。密码必须由环境实际值替换，不要提交到版本库。

```env
DATABASE_URL=postgresql+psycopg://energy_user:<CHANGE_ME>@127.0.0.1:5432/energy_maintenance
```

## 后端启动

进入后端目录后创建虚拟环境、安装依赖、复制环境变量模板并执行数据库迁移。

Windows PowerShell：

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[windows,dev]"
Copy-Item .env.example .env
alembic -c alembic.ini upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Linux：

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
alembic -c alembic.ini upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

后端启动后可访问 `http://127.0.0.1:8000/api/health` 检查服务状态。

## 前端启动

```bash
cd frontend
npm ci
npm run dev
```

生成正式前端构建：

```bash
npm run build
```

开发服务器通过统一的 `/api` 前缀访问后端接口。

## 自动化测试

后端使用 pytest，前端提供类型检查、Lint、单元测试和正式构建检查：

```bash
cd backend
python -m pytest -q
```

```bash
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
```

GitHub Actions 自动执行 `backend`、`frontend` 和 `security` 三个 Job。后端测试强制使用独立测试数据库，不连接正式数据库；CI 中所有外部 Provider 均保持关闭。

## 配置与安全

- `.env`、`.private`、`.local` 仅用于本地配置，不得提交 Git
- 外部服务密钥和密码通过环境变量配置
- 外部 Provider 默认关闭，必须经过显式配置和授权才能启用
- 正式环境必须更换 `SECRET_KEY` 和管理员密码
- 上传文件、运行日志和数据库备份必须按权限受控保存
- 禁止在源码、日志和构建产物中写入真实凭据

## 当前支持范围

- Huawei：SUN2000、FusionSolar
- Sungrow：SG 系列
- 当前设备类型：`pv_inverter`
- 检索结果必须来自真实知识文档和知识切片
- 知识不足时执行受控拒答，不生成虚假 Citation，不跨厂家引用

## 开源与使用说明

本项目用于新能源设备检修知识检索与作业辅助。系统输出不能替代现场工程判断、制造商技术资料、电气安全规程或组织内部审批流程；涉及停送电、故障处置和设备操作时，应由具备资质的人员按正式安全规范执行。
