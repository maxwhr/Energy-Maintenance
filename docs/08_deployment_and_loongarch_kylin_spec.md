# 08 龙芯 LoongArch + 麒麟 Kylin 原生部署规格文档

## Task 16 Deployment Hardening Addendum

Formal deployment target remains `LoongArch + Kylin + Python virtual environment + native PostgreSQL + systemd + Nginx`.

Task 16 adds these delivery helpers:

- `scripts/check_environment_windows.ps1`
- `scripts/fix_postgresql_service_admin.ps1`
- `scripts/start_postgresql_standalone.ps1`
- `scripts/start_all_windows.ps1`
- `scripts/stop_all_windows.ps1`
- `scripts/final_smoke_test.ps1`
- `scripts/check_loongarch_kylin.sh`

Windows notes:

- `start_postgresql_standalone.ps1` uses `D:\Work Space\PostgreSQL\bin\pg_ctl.exe` and `D:\Work Space\PostgreSQL\data` as a local development fallback.
- `fix_postgresql_service_admin.ps1 -Apply` requires Administrator PowerShell and repairs native PostgreSQL service startup.
- `start_all_windows.ps1` checks `alembic current`, repairs or creates the admin user, and starts Uvicorn. It does not execute `alembic upgrade head`.

LoongArch/Kylin notes:

- `scripts/check_loongarch_kylin.sh` is read-only.
- It checks architecture, Kylin markers, Python, pip, uv, Node, npm, psql, PostgreSQL service visibility, gcc, make, systemd, and Nginx.
- It does not install software, modify services, or execute migrations.
- Docker is not required and is not the formal deployment route.
- llama.cpp / GGUF is an optional model-service route only and is not forced by the check script.

Frontend packaging policy:

- `frontend/` is the active source tree.
- `backend/static/frontend/` is generated output installed by `backend/scripts/build_and_install_frontend.ps1`.
- Final release packages must not include `frontend_legacy_before_cupProject_*`.

**Document Name:** `08_deployment_and_loongarch_kylin_spec.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Deployment Target:** LoongArch + Kylin  
**Deployment Strategy:** Native Deployment, No Docker for Final Deployment  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版在龙芯 LoongArch + 麒麟 Kylin 环境下的正式部署方案、运行目录、依赖安装、数据库配置、后端服务、前端部署、Nginx 反向代理、systemd 服务、日志、备份和验收标准。

本项目第一版已经明确为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

部署目标不是普通 x86 开发环境，也不是临时 Docker 演示环境，而是面向国产化软硬件环境：

```text
国产 CPU：LoongArch / 龙芯
国产操作系统：Kylin / 麒麟
国产化运行路线：Python venv + PostgreSQL + systemd + Nginx
```

本文档的核心要求是：

```text
正式部署不使用 Docker
正式部署不依赖 docker-compose
正式部署不依赖 x86-only 本地模型
正式部署优先使用兼容 LoongArch 的 Python 依赖
正式部署以 PostgreSQL 原生服务作为数据库
```

---

## 2. 部署总原则

### 2.1 正式部署路线

正式部署路线固定为：

```text
LoongArch + Kylin
    ↓
系统级 Python / 自编译 Python
    ↓
项目虚拟环境 venv
    ↓
FastAPI + Uvicorn
    ↓
systemd 托管后端服务
    ↓
PostgreSQL 原生服务
    ↓
Nginx 托管前端静态文件并反向代理 API
```

---

### 2.2 不使用 Docker 作为正式路线

第一版最终部署禁止将 Docker 作为正式部署方案。

禁止：

```text
1. 使用 Dockerfile 作为正式部署入口
2. 使用 docker-compose 启动正式服务
3. 依赖 PostgreSQL Docker 容器作为正式数据库
4. 在正式部署文档中把 Docker 写成推荐方案
5. 以“容器能跑”为正式验收标准
```

允许：

```text
1. 本地开发阶段临时连接任意可用 PostgreSQL 实例
2. 本地开发阶段为了验证数据库迁移临时使用已有 PostgreSQL 容器
3. 但必须明确这不是 Energy-Maintenance 的正式部署路线
```

---

### 2.3 部署目标优先级

部署目标按优先级排序：

```text
1. 系统能在 LoongArch + Kylin 原生运行
2. PostgreSQL 能原生安装、启动、连接
3. FastAPI 后端能通过 systemd 常驻运行
4. Vue 前端能通过 Nginx 静态托管
5. /api 接口能通过 Nginx 代理访问
6. 文件上传目录、日志目录和数据库备份可管理
7. 知识库、检索问答、故障诊断和任务记录能真实闭环
```

---

## 3. 目标部署拓扑

推荐单机部署拓扑：

```text
用户浏览器
    ↓
Nginx :80 / :443
    ├── /                 -> frontend/dist 静态文件
    └── /api/*            -> FastAPI / Uvicorn :8000
                              ↓
                         PostgreSQL :5432
                              ↓
                     storage/uploads 文件目录
                              ↓
                     logs 后端日志目录
```

第一版不强制做集群部署、负载均衡、分布式对象存储和高可用数据库。

---

## 4. 服务器基础环境

### 4.1 推荐系统

```text
CPU 架构：LoongArch64
操作系统：Kylin Server / Kylin Advanced Server
内核：以实际服务器为准
数据库：PostgreSQL 14+
Python：3.10+
Node.js：18+ 或 20+
Nginx：1.20+
```

说明：

- Python 版本建议 3.10 或 3.11；
- Node.js 只用于前端构建，构建完成后运行时不依赖 Node；
- PostgreSQL 推荐使用系统包或官方兼容源安装；
- 如果系统仓库版本较旧，应优先选择稳定可用版本，而不是盲目追求最新版。

---

### 4.2 部署用户

建议创建独立运行用户：

```bash
sudo useradd -r -m -d /opt/energy-maintenance -s /bin/bash energy
```

项目正式目录：

```text
/opt/energy-maintenance
```

运行用户：

```text
energy
```

不建议长期使用 root 直接运行后端服务。

---

## 5. 目录规划

推荐目录结构：

```text
/opt/energy-maintenance/
├── app/                         # 项目代码
│   ├── backend/
│   └── frontend/
├── venv/                        # Python 虚拟环境
├── storage/
│   ├── uploads/                 # 上传文件
│   ├── samples/                 # 样例资料
│   └── tmp/                     # 临时文件
├── logs/
│   ├── backend/
│   ├── nginx/
│   └── alembic/
├── backups/
│   ├── database/
│   └── uploads/
└── scripts/
    ├── deploy_backend.sh
    ├── deploy_frontend.sh
    ├── backup_database.sh
    └── health_check.sh
```

权限建议：

```bash
sudo chown -R energy:energy /opt/energy-maintenance
sudo chmod -R 750 /opt/energy-maintenance
```

上传目录应允许后端服务写入：

```bash
sudo mkdir -p /opt/energy-maintenance/storage/uploads
sudo chown -R energy:energy /opt/energy-maintenance/storage
```

---

## 6. 系统依赖安装

### 6.1 基础依赖

示例命令，实际包名以 Kylin 仓库为准：

```bash
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  gcc \
  g++ \
  make \
  libpq-dev \
  postgresql \
  postgresql-contrib \
  nginx \
  curl \
  git
```

如果 Kylin 使用 yum/dnf 系列包管理，应按实际系统替换：

```bash
sudo yum install -y python3 python3-pip gcc gcc-c++ make postgresql postgresql-server nginx curl git
```

---

### 6.2 Node.js

前端构建需要 Node.js。

推荐：

```text
Node.js 18 LTS 或 Node.js 20 LTS
```

如果 Kylin 仓库中 Node 版本过旧，可考虑：

```text
1. 使用系统可用的 Node.js LTS 包
2. 从官方适配包安装
3. 在其他兼容环境构建 frontend/dist 后上传到服务器
```

正式运行时只需要 `frontend/dist`，不需要 Node 常驻运行。

---

## 7. PostgreSQL 原生部署

### 7.1 PostgreSQL 初始化

如果 PostgreSQL 未初始化，需要先初始化数据库目录。

不同 Kylin 版本命令可能不同，常见方式：

```bash
sudo postgresql-setup initdb
```

或：

```bash
sudo /usr/bin/postgresql-setup --initdb
```

启动服务：

```bash
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo systemctl status postgresql
```

如果服务名不是 `postgresql`，需要用实际服务名，例如：

```text
postgresql-14
postgresql-15
```

---

### 7.2 创建数据库和用户

切换到 postgres 用户：

```bash
sudo -u postgres psql
```

执行：

```sql
CREATE USER energy_user WITH PASSWORD 'energy_password';
CREATE DATABASE energy_maintenance OWNER energy_user;
GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;
```

建议生产环境使用更强密码，不要使用示例密码。

退出：

```sql
\q
```

---

### 7.3 连接测试

```bash
psql "postgresql://energy_user:energy_password@127.0.0.1:5432/energy_maintenance"
```

成功进入 psql 后执行：

```sql
SELECT version();
```

必须能返回 PostgreSQL 版本信息。

---

### 7.4 数据库连接环境变量

后端 `.env` 中应配置：

```env
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:5432/energy_maintenance
```

不得在代码中写死该连接。

---

### 7.5 PostgreSQL 配置注意事项

如果后端和数据库在同一台服务器：

```text
listen_addresses 可保持 localhost
```

如果需要远程连接数据库，才需要修改：

```text
postgresql.conf
pg_hba.conf
```

第一版推荐同机部署，减少安全风险。

---

## 8. 后端部署

### 8.1 后端目录

后端代码位于：

```text
/opt/energy-maintenance/app/backend
```

---

### 8.2 创建 Python 虚拟环境

```bash
cd /opt/energy-maintenance
python3 -m venv venv
source venv/bin/activate
python -V
pip -V
```

---

### 8.3 安装依赖

如果项目使用 `pyproject.toml`：

```bash
cd /opt/energy-maintenance/app/backend
pip install -U pip setuptools wheel
pip install -e .
```

如果使用 `requirements.txt`：

```bash
pip install -r requirements.txt
```

如果使用 `uv`，需要确认 uv 在 LoongArch + Kylin 可用。若 uv 不可用，正式部署优先使用标准 venv + pip。

---

### 8.4 LoongArch 依赖选择要求

优先使用纯 Python 或 LoongArch 易编译依赖：

```text
fastapi
uvicorn
sqlalchemy
alembic
pydantic
pydantic-settings
psycopg
python-multipart
pypdf
python-docx
```

谨慎使用：

```text
PyMuPDF
paddleocr
opencv
faiss
onnxruntime
torch
大型本地 embedding 模型
```

原因：

```text
1. LoongArch 编译或运行兼容性存在不确定性
2. 第一版不需要依赖这些组件打通主闭环
3. 本项目优先保证检修知识库和问答链路稳定部署
```

---

### 8.5 后端环境变量

后端 `.env` 示例：

```env
APP_NAME=Energy-Maintenance
APP_ENV=production
APP_VERSION=0.1.0

HOST=127.0.0.1
PORT=8000

DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:5432/energy_maintenance

UPLOAD_DIR=/opt/energy-maintenance/storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_DOCUMENT_EXTENSIONS=txt,md,pdf,docx

DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=150

LOG_DIR=/opt/energy-maintenance/logs/backend
```

说明：

- `HOST` 建议绑定 `127.0.0.1`，由 Nginx 对外暴露；
- 不建议后端直接暴露到公网；
- `.env` 不应提交到公开仓库；
- 仓库中只保留 `.env.example`。

---

### 8.6 数据库迁移

执行 Alembic 迁移：

```bash
cd /opt/energy-maintenance/app/backend
source /opt/energy-maintenance/venv/bin/activate
alembic -c alembic.ini upgrade head
```

如果使用 uv：

```bash
uv run alembic -c alembic.ini upgrade head
```

但正式部署不应依赖 uv 必须存在。

迁移成功后检查表：

```bash
psql "postgresql://energy_user:energy_password@127.0.0.1:5432/energy_maintenance" -c "\dt"
```

必须能看到：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

---

### 8.7 后端手动启动测试

```bash
cd /opt/energy-maintenance/app/backend
source /opt/energy-maintenance/venv/bin/activate

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

测试：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/system/status
```

必须返回正常 JSON。

---

## 9. systemd 后端服务

### 9.1 服务文件路径

```text
/etc/systemd/system/energy-maintenance-backend.service
```

### 9.2 服务文件示例

```ini
[Unit]
Description=Energy-Maintenance FastAPI Backend
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=energy
Group=energy
WorkingDirectory=/opt/energy-maintenance/app/backend
EnvironmentFile=/opt/energy-maintenance/app/backend/.env
ExecStart=/opt/energy-maintenance/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=append:/opt/energy-maintenance/logs/backend/backend.out.log
StandardError=append:/opt/energy-maintenance/logs/backend/backend.err.log

[Install]
WantedBy=multi-user.target
```

如系统 systemd 版本不支持 `append:`，可使用 journald：

```ini
StandardOutput=journal
StandardError=journal
```

---

### 9.3 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable energy-maintenance-backend
sudo systemctl start energy-maintenance-backend
sudo systemctl status energy-maintenance-backend
```

查看日志：

```bash
journalctl -u energy-maintenance-backend -f
```

或：

```bash
tail -f /opt/energy-maintenance/logs/backend/backend.out.log
tail -f /opt/energy-maintenance/logs/backend/backend.err.log
```

---

### 9.4 后端服务验收

```bash
curl http://127.0.0.1:8000/api/health
```

必须返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "running"
  }
}
```

---

## 10. 前端部署

### 10.1 前端构建

进入前端目录：

```bash
cd /opt/energy-maintenance/app/frontend
npm install
npm run build
```

构建产物：

```text
frontend/dist
```

如果 LoongArch 服务器上 Node 构建有问题，可在兼容环境构建后上传 `dist` 目录。

但必须保证：

```text
构建产物与当前 API 路径 /api 一致
```

---

### 10.2 前端环境变量

前端不应写死后端地址。

推荐使用相对路径：

```text
/api
```

生产环境中由 Nginx 反向代理。

---

### 10.3 前端静态目录

推荐部署路径：

```text
/opt/energy-maintenance/app/frontend/dist
```

权限：

```bash
sudo chown -R energy:energy /opt/energy-maintenance/app/frontend/dist
```

Nginx 用户需要具备读取权限。

---

## 11. Nginx 配置

### 11.1 配置文件路径

建议：

```text
/etc/nginx/conf.d/energy-maintenance.conf
```

或 Kylin 默认站点目录：

```text
/etc/nginx/sites-available/energy-maintenance
/etc/nginx/sites-enabled/energy-maintenance
```

以实际 Nginx 配置结构为准。

---

### 11.2 Nginx 配置示例

```nginx
server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    root /opt/energy-maintenance/app/frontend/dist;
    index index.html;

    access_log /opt/energy-maintenance/logs/nginx/access.log;
    error_log  /opt/energy-maintenance/logs/nginx/error.log;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_read_timeout 300;
        proxy_connect_timeout 60;
        proxy_send_timeout 300;
    }
}
```

注意：

```text
/api/ 转发必须保持路径一致。
前端请求 /api/health 时，应代理到后端 /api/health。
```

---

### 11.3 测试 Nginx 配置

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo systemctl enable nginx
sudo systemctl status nginx
```

浏览器访问：

```text
http://服务器IP/
```

接口访问：

```text
http://服务器IP/api/health
```

---

## 12. 文件上传目录

### 12.1 上传目录

生产环境上传目录：

```text
/opt/energy-maintenance/storage/uploads
```

`.env` 中：

```env
UPLOAD_DIR=/opt/energy-maintenance/storage/uploads
```

---

### 12.2 权限要求

```bash
sudo chown -R energy:energy /opt/energy-maintenance/storage/uploads
sudo chmod -R 750 /opt/energy-maintenance/storage/uploads
```

---

### 12.3 上传目录备份

上传资料属于知识库重要数据，应定期备份。

推荐备份路径：

```text
/opt/energy-maintenance/backups/uploads
```

备份命令示例：

```bash
tar -czf /opt/energy-maintenance/backups/uploads/uploads_$(date +%Y%m%d_%H%M%S).tar.gz \
  -C /opt/energy-maintenance/storage uploads
```

---

## 13. 日志规划

### 13.1 后端日志

路径：

```text
/opt/energy-maintenance/logs/backend
```

内容：

```text
backend.out.log
backend.err.log
application.log，可选
```

日志应至少包含：

```text
启动信息
数据库连接异常
文档上传异常
文档解析异常
问答 trace_id
诊断 trace_id
任务创建和状态更新异常
```

---

### 13.2 Nginx 日志

路径：

```text
/opt/energy-maintenance/logs/nginx
```

内容：

```text
access.log
error.log
```

---

### 13.3 日志轮转

建议配置 logrotate，避免日志无限增长。

示例：

```text
/opt/energy-maintenance/logs/backend/*.log
/opt/energy-maintenance/logs/nginx/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
    copytruncate
}
```

---

## 14. 数据库备份

### 14.1 手动备份

```bash
pg_dump -U energy_user -h 127.0.0.1 -p 5432 energy_maintenance \
  > /opt/energy-maintenance/backups/database/energy_maintenance_$(date +%Y%m%d_%H%M%S).sql
```

如果需要输入密码，可设置：

```bash
export PGPASSWORD='energy_password'
```

---

### 14.2 恢复备份

```bash
psql -U energy_user -h 127.0.0.1 -p 5432 energy_maintenance \
  < /opt/energy-maintenance/backups/database/energy_maintenance_YYYYMMDD_HHMMSS.sql
```

恢复前必须确认当前数据库状态，避免误覆盖。

---

### 14.3 自动备份脚本

建议创建：

```text
/opt/energy-maintenance/scripts/backup_database.sh
```

示例：

```bash
#!/usr/bin/env bash
set -e

BACKUP_DIR="/opt/energy-maintenance/backups/database"
mkdir -p "$BACKUP_DIR"

export PGPASSWORD="energy_password"

pg_dump -U energy_user -h 127.0.0.1 -p 5432 energy_maintenance \
  > "$BACKUP_DIR/energy_maintenance_$(date +%Y%m%d_%H%M%S).sql"
```

权限：

```bash
chmod +x /opt/energy-maintenance/scripts/backup_database.sh
```

---

### 14.4 定时备份

使用 cron：

```bash
crontab -e
```

示例：每天凌晨 2 点备份。

```text
0 2 * * * /opt/energy-maintenance/scripts/backup_database.sh
```

---

## 15. 发布更新流程

### 15.1 后端更新流程

```bash
cd /opt/energy-maintenance/app
git pull

cd backend
source /opt/energy-maintenance/venv/bin/activate
pip install -e .

alembic -c alembic.ini upgrade head

sudo systemctl restart energy-maintenance-backend
sudo systemctl status energy-maintenance-backend
```

验收：

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/system/status
```

---

### 15.2 前端更新流程

```bash
cd /opt/energy-maintenance/app/frontend
npm install
npm run build
sudo systemctl reload nginx
```

访问：

```text
http://服务器IP/
```

---

### 15.3 更新前备份

更新前建议执行：

```bash
/opt/energy-maintenance/scripts/backup_database.sh
tar -czf /opt/energy-maintenance/backups/uploads/uploads_before_deploy_$(date +%Y%m%d_%H%M%S).tar.gz \
  -C /opt/energy-maintenance/storage uploads
```

---

## 16. 安全配置

### 16.1 后端绑定本机

后端 Uvicorn 应绑定：

```text
127.0.0.1:8000
```

由 Nginx 对外代理。

不建议直接：

```text
0.0.0.0:8000
```

暴露后端。

---

### 16.2 .env 权限

```bash
chmod 600 /opt/energy-maintenance/app/backend/.env
chown energy:energy /opt/energy-maintenance/app/backend/.env
```

`.env` 中包含数据库密码，禁止提交到仓库。

---

### 16.3 上传文件安全

必须限制：

```text
1. 文件扩展名
2. 文件大小
3. 文件路径穿越
4. 空文件
5. 非文档类型
```

Nginx 中也要限制：

```nginx
client_max_body_size 50M;
```

---

### 16.4 数据库访问安全

第一版推荐数据库仅本机访问：

```text
127.0.0.1:5432
```

不对公网开放 PostgreSQL。

---

## 17. 健康检查脚本

建议创建：

```text
/opt/energy-maintenance/scripts/health_check.sh
```

内容示例：

```bash
#!/usr/bin/env bash
set -e

echo "Checking backend..."
curl -f http://127.0.0.1:8000/api/health

echo "Checking system status..."
curl -f http://127.0.0.1:8000/api/system/status

echo "Checking nginx..."
curl -f http://127.0.0.1/

echo "Health check passed."
```

权限：

```bash
chmod +x /opt/energy-maintenance/scripts/health_check.sh
```

---

## 18. 部署验收标准

### 18.1 系统服务验收

必须满足：

```text
1. PostgreSQL 服务 active
2. energy-maintenance-backend 服务 active
3. Nginx 服务 active
4. /api/health 返回 success
5. /api/system/status 返回 database_status = connected
6. 浏览器能访问前端首页
```

---

### 18.2 数据库迁移验收

必须执行成功：

```bash
alembic -c alembic.ini upgrade head
```

并能看到核心表：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

---

### 18.3 知识库上传验收

上传华为样例文档：

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@/opt/energy-maintenance/storage/samples/sample_huawei_sun2000_low_insulation.txt" \
  -F "manufacturer=huawei" \
  -F "product_series=SUN2000" \
  -F "device_type=pv_inverter" \
  -F "document_type=alarm_code" \
  -F "source=local_sample"
```

必须满足：

```text
parse_status = parsed
chunk_count > 0
knowledge_chunks 写入真实 content
```

---

### 18.4 检索问答验收

```bash
curl -X POST http://127.0.0.1:8000/api/retrieval/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "device_type": "pv_inverter",
    "top_k": 5
  }'
```

必须满足：

```text
answer 不为空
references 不为空
retrieved_chunks 不为空
qa_records 写入成功
```

---

### 18.5 故障诊断验收

```bash
curl -X POST http://127.0.0.1:8000/api/diagnosis/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer": "sungrow",
    "product_series": "SG",
    "device_type": "pv_inverter",
    "fault_type": "over_temperature",
    "fault_description": "阳光 SG 系列逆变器中午高温时频繁出现过温降额。"
  }'
```

必须满足：

```text
possible_causes 不为空
inspection_steps 不为空
safety_notes 不为空
diagnosis_records 写入成功
```

---

### 18.6 前端验收

浏览器访问：

```text
http://服务器IP/
```

必须满足：

```text
1. Dashboard 正常打开
2. 知识库页面可上传资料
3. 检修问答页面可展示 answer 和 references
4. 故障诊断页面可展示安全提示
5. 检修任务页面可创建任务
6. 系统状态页显示数据库连接状态
```

---

## 19. 常见问题与处理

### 19.1 PostgreSQL 连接失败

检查：

```bash
systemctl status postgresql
ss -lntp | grep 5432
psql "postgresql://energy_user:energy_password@127.0.0.1:5432/energy_maintenance"
```

常见原因：

```text
1. PostgreSQL 未启动
2. 用户名或密码错误
3. 数据库未创建
4. pg_hba.conf 不允许连接
5. DATABASE_URL 写错
```

---

### 19.2 Alembic 找不到模型

检查：

```text
backend/alembic/env.py
SQLAlchemy Base.metadata
models 是否被导入
```

必须确保 Alembic 能识别所有表。

---

### 19.3 前端能打开但 API 失败

检查：

```bash
curl http://127.0.0.1:8000/api/health
curl http://服务器IP/api/health
nginx -t
journalctl -u energy-maintenance-backend -f
tail -f /opt/energy-maintenance/logs/nginx/error.log
```

常见原因：

```text
1. Nginx /api 代理路径错误
2. 后端服务未启动
3. 后端绑定地址错误
4. 防火墙或端口策略
```

---

### 19.4 上传失败

检查：

```text
1. UPLOAD_DIR 是否存在
2. energy 用户是否有写权限
3. Nginx client_max_body_size 是否过小
4. 文件扩展名是否支持
5. 后端日志中的 parser 错误
```

---

### 19.5 PDF 解析为空

可能原因：

```text
1. 扫描版 PDF
2. PDF 中主要是图片
3. pypdf 无法提取版式文本
```

第一版处理：

```text
parse_status = failed
error_message = extracted text is empty
```

不应假装解析成功。

---

## 20. 与开发环境的关系

本地开发可临时使用：

```text
Windows
已有 PostgreSQL
临时 PostgreSQL 容器
本地 Node.js
本地 uv
```

但必须明确：

```text
本地开发方式不等于正式部署方式
```

正式部署仍然是：

```text
LoongArch + Kylin + venv + native PostgreSQL + systemd + Nginx
```

---

## 21. 与其他文档关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
03_database_schema_design.md
04_api_contract_design.md
05_frontend_page_and_interaction_spec.md
06_knowledge_base_and_document_processing_spec.md
07_retrieval_qa_and_fault_diagnosis_spec.md
```

其中：

- `01` 确定项目范围；
- `02` 确定技术架构；
- `03` 确定数据库结构；
- `04` 确定 API 契约；
- `05` 确定前端交互；
- `06` 确定知识库处理；
- `07` 确定检索问答和故障诊断；
- `08` 确定正式部署路线。

---

## 22. 下一步建议

本文档确认后，下一份建议编写：

```text
09_testing_acceptance_and_quality_spec.md
```

下一份文档应重点定义：

```text
功能测试
接口测试
数据库真实闭环测试
前端页面验收
知识库上传验收
检索问答验收
故障诊断验收
检修任务验收
LoongArch 部署验收
代码质量和禁止事项
```
---

## Task 02A 部署路线一致性补充

正式部署路线保持 LoongArch + Kylin 原生部署。

### A. 正式部署组件

- Python virtual environment。
- FastAPI + Uvicorn。
- native PostgreSQL service。
- Nginx。
- systemd。
- 前端静态资源由 Nginx 托管。

### B. 模型服务部署边界

本地小模型优先使用 llama.cpp + GGUF，并通过统一 Model Gateway 接入业务系统。云端模型通过 OpenAI-compatible API 作为可配置路径接入。业务模块不得直接绑定某个模型运行时或云 SDK。

### C. OCR 与依赖兼容性

OCR 通过 OCRService 抽象预留，PaddleOCR、RapidOCR、Tesseract 等具体引擎需要在 LoongArch + Kylin 环境验证后再纳入正式部署清单。

### D. 非正式部署路线

Docker 和 docker-compose 不作为正式部署路线。SQLite 不作为正式数据库。Neo4j、Milvus、FAISS、Chroma、vLLM 不作为第一版本部署硬依赖。

---

## Task 12 补充：模型服务部署边界

Model Gateway 的正式部署边界如下：

- 后端进程内置 `rule_based` provider，作为无需外部服务的兜底路径。
- 本地小模型仅预留 `local_llama_cpp` HTTP 接入方式，实际 llama.cpp、GGUF 模型文件、服务守护方式由后续部署任务单独验收。
- 云端模型仅预留 OpenAI-compatible API 配置项，不在部署文档中写死厂商、API key 或公网地址。
- `.env` 中 `LOCAL_LLM_ENABLED=false`、`CLOUD_LLM_ENABLED=false` 是默认安全配置。
- 如果后续启用本地模型服务，应使用 LoongArch + Kylin 可运行的原生服务或 systemd 托管方式，不把 Docker 写成正式路线。
- 如果后续启用云端模型，API key 只允许保存在服务器 `.env` 或受控密钥系统中，不进入前端构建产物、日志和仓库。

本补充不要求安装 llama.cpp，不要求下载 GGUF，不要求执行云端模型调用。

---

## Task 14A 补充：部署前环境自检

Task 14A 只补充部署前自检能力，不执行 LoongArch + Kylin 实机部署。

### A. 自检脚本

项目根目录提供：

```bash
scripts/loongarch_env_check.sh
```

该脚本为只读检查，输出：

```text
1. 操作系统信息
2. CPU 架构
3. python3 / pip3
4. node / npm
5. psql
6. nginx
7. systemctl
8. PostgreSQL / Nginx / energy-maintenance 相关 systemd unit 线索
```

脚本不会安装软件、不会修改 systemd、不会启动或停止服务。

### B. 正式部署仍需人工确认

正式部署前需要在目标机器确认：

```text
1. 架构为 loongarch64
2. Kylin 系统包源可用
3. Python 3.10+ 可创建 venv
4. Node.js / npm 可完成前端 build
5. PostgreSQL 原生服务可用
6. Nginx 可托管前端静态资源并反向代理 /api
7. systemd 可托管后端服务
8. 上传目录、日志目录、备份目录权限正确
```

### C. Model Gateway 部署边界

当前默认模型 provider 仍为：

```text
rule_based
```

`local_llama_cpp` 和 `cloud_openai` 仅作为可配置接入路径。Task 14A 不安装 llama.cpp、不下载 GGUF、不调用云端模型。

Task 14B 允许通过 `cloud_openai` 执行 OpenAI-compatible API 联调，但仍不改变正式部署路线。云端模型配置必须放在 `backend/.env`，不得写入 systemd unit、Nginx 配置、代码仓库或报告正文。若 `CLOUD_LLM_*` 未完整配置，验收结果必须标记为 `blocked`。

真实本地模型或云端模型联调应进入后续：

```text
Task 14B 或 Task 15
```

### D. 禁止路线

正式部署文档继续禁止将 Docker、docker-compose、SQLite、pgvector、OCR 或重型模型运行时写成第一版本硬依赖。
# Task 18F Addendum: Local llama.cpp / GGUF Preparation

Local llama.cpp is an optional enhancement path for LoongArch + Kylin. It is not required for the first-version core closed loop.

## Build Preparation

On the target LoongArch/Kylin host, prepare the native toolchain before attempting local inference:

```bash
gcc --version
g++ --version
cmake --version
make --version
git --version
```

Compile llama.cpp from source according to the upstream llama.cpp documentation and the target machine capability. This repository does not vendor llama.cpp and does not download model files.

## GGUF Model Placement

Recommended policy:

- store GGUF files outside the repository, for example under `/opt/energy-maintenance/models`.
- grant read permission only to the service user.
- do not commit `.gguf`, `.bin`, or `.safetensors` files.
- in reports and logs, record only a model label, not the full file path.

For small CPU-only machines, prefer a small Q4 quantized model. On 8GB memory hosts, large models may be too slow or fail to load.

## llama-server Startup

Example only:

```bash
./llama-server -m /path/to/model.gguf --host 127.0.0.1 --port 8080
```

The repository provides example templates:

```text
scripts/start_llama_cpp_server_example.ps1
scripts/start_llama_cpp_server_example.sh
```

They do not install llama.cpp and do not provide a model.

## Energy-Maintenance Configuration

Configure local `.env` only when a local service exists:

```env
LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080
LOCAL_LLM_MODEL=<model-label-or-local-name>
LOCAL_LLM_API_TYPE=openai_compatible
LOCAL_LLM_TIMEOUT_SECONDS=60
LOCAL_LLM_MAX_TOKENS=1024
LOCAL_LLM_TEMPERATURE=0.2
LOCAL_LLM_HEALTH_PATH=/health
LOCAL_LLM_NATIVE_COMPLETION_PATH=/completion
LOCAL_LLM_OPENAI_CHAT_PATH=/v1/chat/completions
```

Use `LOCAL_LLM_API_TYPE=llama_cpp_native` only when calling the llama.cpp native `/completion` endpoint.

## Validation

After backend startup:

```bash
cd backend
uv run python scripts/check_local_llama_cpp_flow.py
```

Acceptance interpretation:

- `passed`: local llama.cpp is reachable and real calls succeed.
- `blocked`: local llama.cpp is disabled or unreachable; rule-based fallback is verified.
- `failed`: local llama.cpp is configured but calls, logging, or safety checks fail.

If local llama.cpp is unavailable, Energy-Maintenance must continue to run through `rule_based` fallback.

# Task 18H Addendum: Final Target Acceptance

Task 18H freezes the current Windows-validated package and prepares target-machine acceptance. Windows validation is not a substitute for real LoongArch/Kylin execution.

## Target Host Required Checks

Run on the target host:

```bash
cd /path/to/Energy-Maintenance
bash scripts/check_loongarch_kylin.sh
```

Record:

```bash
uname -m
cat /etc/os-release
python3 --version
node --version
npm --version
psql --version
systemctl status postgresql
free -h
df -h
```

The expected architecture is:

```text
loongarch64
```

## Deployment Smoke

After configuring `backend/.env`, PostgreSQL, and the admin account:

```bash
cd backend
uv sync
uv run python -m alembic -c alembic.ini upgrade head
uv run python scripts/seed_final_demo_data.py
uv run python scripts/create_admin_user.py

cd ../frontend
npm install
npm run build

cd ../backend
bash scripts/build_and_install_frontend.sh
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another shell:

```bash
cd /path/to/Energy-Maintenance
API_BASE_URL=http://127.0.0.1:8000 bash scripts/final_smoke_test.sh
```

## Acceptance State Rules

- If all target checks pass, record LoongArch/Kylin acceptance as `passed`.
- If no target host is available, record LoongArch/Kylin acceptance as `blocked`.
- Do not report `passed` based only on Windows validation.
- Do not introduce Docker, SQLite, pgvector, embedding, external graph databases, model binaries, or OCR binaries into the first-version deployment package.

# Task 18G Addendum: Optional Tesseract OCR

OCR is an optional media-evidence helper and is disabled by default. It is not a mandatory deployment component for the first-version Huawei/Sungrow PV inverter closed loop.

Recommended environment check on LoongArch/Kylin:

```bash
./scripts/check_tesseract_env.sh
```

If OCR is enabled later, configure only local environment variables:

```env
OCR_ENABLED=true
OCR_PROVIDER=tesseract
OCR_LANG=chi_sim+eng
OCR_TIMEOUT_SECONDS=30
OCR_MAX_IMAGE_MB=10
OCR_TESSERACT_CMD=tesseract
```

Acceptance interpretation:

- `available`: Tesseract command and required language data are visible.
- `not_configured`: Tesseract or required languages are missing; report OCR as blocked.
- `disabled`: OCR is intentionally off and should not be treated as a failure.

Deployment boundary:

- OCR extracts image text only; it is not image fault recognition.
- OCR text must remain optional context and must not become approved knowledge automatically.
- Do not add PaddleOCR, RapidOCR, deep-learning OCR runtimes, Docker, SQLite, pgvector, or embedding as first-version deployment requirements.

## Task 24D Addendum: Production Security Baseline

Before production startup on LoongArch + Kylin, set strong values for `SECRET_KEY` and `ADMIN_PASSWORD`, configure PostgreSQL `DATABASE_URL`, configure formal CORS origins, and verify upload/log directories are writable by the service account.

Do not deploy with wildcard CORS, placeholder secrets, weak admin passwords, or real providers marked enabled without complete `base_url` / `api_key` / `model` configuration. Use Nginx or an upstream gateway for production-grade rate limiting; the application-level in-memory limiter is a single-instance safety net.

Previously exposed real API keys must be rotated before any production or real-call acceptance.
