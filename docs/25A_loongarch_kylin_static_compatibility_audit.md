# Task 25A LoongArch / 银河麒麟静态兼容审计

> 结论：**high_risk**。这是静态审计，不是实机通过。最大风险是原生/Rust 包、Vite/Rolldown 平台二进制、缺少正式 systemd/Nginx 产物以及四核 8GB 未压测。

## 1. 依赖基线

- Python：>=3.10；锁定包 35 个。
- npm lock package entries：149。
- PowerShell：28；shell：14。
- 正式运行建议预构建前端，目标机只运行 Nginx + FastAPI + PostgreSQL；但仍必须在目标机验证 Python native/Rust 依赖。

## 2. 三十项静态审计

| # | item | conclusion | evidence / gap |
|---:|---|---|---|
| 1 | Python 版本 | likely_compatible | >=3.10；需在目标仓库确认可安装版本。 |
| 2 | FastAPI | likely_compatible | 主要为 Python；受 pydantic-core/Starlette 依赖影响。 |
| 3 | Uvicorn | requires_build | uvicorn[standard] 锁定 httptools/uvloop/watchfiles/websockets，可能无 LoongArch wheel。 |
| 4 | Psycopg | requires_build | 需目标机 libpq/PostgreSQL client library；未使用 psycopg-binary。 |
| 5 | PostgreSQL | likely_compatible | 正式路线为麒麟 native service；本轮仅 Windows 55432 验证。 |
| 6 | PDF 解析库 | static_compatible | pypdf 为纯 Python；扫描 PDF 仍需 OCR。 |
| 7 | DOCX 解析库 | requires_build | python-docx 依赖 lxml，需要 LoongArch libxml2/libxslt 或源码构建。 |
| 8 | Pillow | unknown | 当前直接依赖未声明；图像链路主要保存/转发，后续引入需重新审计。 |
| 9 | OCR 依赖 | high_risk | Tesseract 是系统二进制与语言包；OCR API 可绕过本地引擎但依赖网络。 |
| 10 | 浏览器测试依赖 | high_risk | Node browser 脚本存在；目标机无浏览器/驱动验收。 |
| 11 | Node.js | unknown | 正式运行可仅托管预构建静态文件；目标机源码构建版本未确认。 |
| 12 | npm 包 | high_risk | Vite 8/Rolldown 锁含平台二进制包，未见 LoongArch binding。 |
| 13 | 前端构建结果 | static_compatible | Windows npm build 与静态安装通过；产物可由 Nginx/后端托管。 |
| 14 | shell/PowerShell | requires_build | 19 个 PowerShell 与 14 个 shell 文件；Linux 需只使用 .sh 等价路径。 |
| 15 | Windows 路径硬编码 | high_risk | 多份运维/测试脚本含 D:\Work Space 或本机端口。 |
| 16 | 反斜杠路径 | requires_build | Python 生产代码多用 pathlib，但 Windows check 脚本不可直接搬迁。 |
| 17 | Windows 服务调用 | requires_build | Get-Service/Start-Process 等仅本机运维；生产需 systemd。 |
| 18 | exe 调用 | requires_build | PowerShell 脚本调用 .exe；Linux 必须走无后缀命令与 systemd。 |
| 19 | native wheel | high_risk | httptools: native extension; wheel availability must be confirmed on LoongArch; greenlet: native extension used by SQLAlchemy; LoongArch wheel or compiler toolchain must be confirmed; lxml: native XML extension required by python-docx; libxml2/libxslt headers and a LoongArch build may be required; psycopg: pure-Python package still requires a usable libpq implementation on the target host; pyyaml: contains an optional C extension; source build behavior must be verified; uvloop: native extension and platform-specific event loop; optional on unsupported platforms; watchfiles: Rust/native extension; LoongArch wheel availability may require source build; websockets: may use optimized native components depending on release; runtime install must be verified; pydantic-core: Rust extension; LoongArch wheel availability is a hard installation check |
| 20 | x86_64-only wheel | unknown | 锁文件包含 Windows/x64 npm binding；Python wheel 平台选择未实机解析。 |
| 21 | CUDA/GPU | static_compatible | 核心依赖未要求 CUDA/GPU；符合 CPU-first 方向。 |
| 22 | Docker | static_compatible | 未发现 Dockerfile/compose；正式路线非 Docker。 |
| 23 | gcc/g++/Rust | requires_build | pydantic-core/watchfiles/greenlet/lxml 可能需要编译器，部分包需要 Rust。 |
| 24 | 系统库 | requires_build | PostgreSQL/libpq、libxml2/libxslt、Tesseract/language pack 需系统包。 |
| 25 | 可能无法安装的包 | high_risk | pydantic-core、uvloop、httptools、watchfiles、lxml 与 Rolldown binding 是重点。 |
| 26 | systemd 启动 | high_risk | docs 描述了路线，但仓库根未发现 .service 产物。 |
| 27 | Nginx 静态服务 | high_risk | docs 描述了路线，但仓库根未发现 Nginx .conf 产物。 |
| 28 | 文件权限 | unknown | 上传/日志可写校验仅 Windows；麒麟用户、目录、umask 未验证。 |
| 29 | SELinux/安全策略 | unknown | 无麒麟安全策略/端口/目录上下文实测。 |
| 30 | 资源占用 | high_risk | 四核 8GB 未测；本地 record center 并发 p95 1763.863 ms。 |

## 3. 目标机验收门

1. 在 LoongArch + 银河麒麟 V10/V11 建立干净 Python venv，逐个安装锁定依赖并保存 wheel/build 日志。
2. 安装 native PostgreSQL，执行现有 migration 链到 20260601_0008，并核对 42 张表。
3. 增加并验证 systemd service、Nginx 配置、上传/日志目录权限与安全策略。
4. 运行 compile、专项 flow、前端静态服务、final smoke、性能基线和备份恢复。
5. 任何单项未执行均必须标记 unknown/high_risk，不能表述为实机通过。

<!-- TASK25A_R1_CORRECTION_START -->

## Task 25A-R1 更正：依赖用途拆分

R1 于 2026-07-10T13:51:23.944120+00:00 重建证据模型。原 83 项 maturity 是历史审计观察，不再作为当前最终结论。
新统计：VERIFIED=24，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED=36，PARTIAL=16，PLACEHOLDER_OR_MOCK=4，MISSING=3。
新结论以 `.runtime/task25a_r1/evidence_registry.json`、`test_execution_registry.json` 和自动规则为准；历史 real-call、mock、browser、性能和 LoongArch 实机证据不再混写。
依赖已拆分为 runtime required/optional、build、development、test；本轮实机状态仍为 NOT_EXECUTED，不能写通过。

<!-- TASK25A_R1_CORRECTION_END -->
