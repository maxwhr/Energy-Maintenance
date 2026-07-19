# LoongArch/Kylin Native Deployment Audit

## Verdict

The repository has a credible non-Docker native deployment design and unusually detailed source-level preparation. It is `IMPLEMENTED_UNVERIFIED`, not physically accepted. Formal deployment must remain `BLOCKED` until a real `loongarch64` Kylin host completes dependency builds and runtime checks.

## Target Architecture

- CPU: LoongArch64.
- OS: Kylin/Galaxy Kylin with systemd.
- Backend: Python 3.10+ venv, Uvicorn/FastAPI.
- Database: native PostgreSQL 14+.
- Web: Nginx reverse proxy and static SPA.
- Process management: systemd.
- Production frontend: prebuilt assets; no Node/npm runtime dependency.
- Formal Docker dependency: none.

Evidence:

- `deploy/loongarch/README.md:1-20`
- `deploy/loongarch/config/energy-maintenance-backend.service:1-16`
- `deploy/loongarch/config/energy-maintenance.conf`
- `docs/08_deployment_and_loongarch_kylin_spec.md:41-177`

## Deployment Assets Found

| Area | Assets | Audit result |
|---|---|---|
| Platform detection | architecture/Kylin/system tools scripts | Static code and unit checks exist. |
| Directory layout | releases/current/shared/backups/logs/storage | Atomic release layout represented. |
| Python dependencies | pinned LoongArch requirements and risk manifests | Target builds still required. |
| Frontend | prebuilt dist installer | Design avoids production Node/npm. |
| Database | backup-before-upgrade and migration scripts | Not run in this audit. |
| systemd | hardened service template/configure scripts | Not installed/tested on target. |
| Nginx | config/install/validation scripts | Not installed/tested on target. |
| Health checks | local `/api/health`, systemd and Nginx checks | Static checks only. |
| Rollback | current-release switch and backup metadata | Dry-run/unit tests passed; no real target rollback. |
| Acceptance | real-machine checklist | Blank/unexecuted. |

## Service Design

The systemd unit orders after network and PostgreSQL, runs a venv Python Uvicorn process on 127.0.0.1:8012, uses a non-root service account and restarts on failure. Nginx is intended to expose the SPA/API externally.

Evidence: `deploy/loongarch/config/energy-maintenance-backend.service:3-13`.

The health script constrains checks to the local backend, applies curl timeout, verifies the backend service and validates Nginx configuration (`deploy/loongarch/scripts/healthcheck.sh:8-31`).

## Dependency Compatibility

### Lower-risk/pure Python

FastAPI, SQLAlchemy, pypdf, python-docx package code, h11 and psycopg Python package are represented as universal packages. Psycopg still requires native system libpq.

### Target build/system library risks

- `pydantic-core`: Rust/maturin target build.
- `Pillow`: C build plus JPEG/PNG/zlib libraries.
- `lxml`: libxml2/libxslt build required through python-docx.
- `MarkupSafe`: target build or validated pure fallback.
- psycopg: system libpq; `psycopg-binary` is explicitly excluded from production.

Evidence: `deploy/loongarch/manifests/python_dependencies.json` and `native_dependency_risks.json`.

No x86-only mandatory runtime dependency was conclusively found, but availability of a complete LoongArch wheelhouse remains unverified.

## Offline And External Dependencies

- Offline manifests require only `py3-none-any` or `loongarch64` wheels and checksums.
- External model/vector/OCR providers are optional; core keyword retrieval should remain available when they are disabled.
- Current code can attempt real provider calls only under explicit flags, but this audit did not test network-denied production behavior.
- Local llama.cpp and Tesseract are optional and not part of the verified core.

## Backup, Migration And Rollback

The deployment sequence includes pre-upgrade database backup, release layout, migration, health check and rollback. Credentials are passed through the environment rather than printed in the `pg_dump` command. The scripts preserve shared data and do not present uninstall as database deletion.

Unverified:

- actual backup file integrity and restore;
- migration from a clean target database to 0015;
- rollback compatibility after schema changes;
- uploads backup/restore and permissions;
- log rotation under long-running load.

## Current Windows Operational Gap

The local PostgreSQL Windows service is stopped/disabled, while a standalone process serves port 55432. This is not the target Kylin architecture but demonstrates that current local startup is not durable. It should not be used as evidence for production service ordering.

## Static Verification Performed

Seven isolated Task 25G tests passed for runtime portability, rollback safety, real-machine guard, platform detection, offline manifest, dependency classification and atomic release layout. ShellCheck and native Bash/systemd/Nginx execution were not available in this Windows audit.

## Delivery Blockers

1. Git HEAD does not contain the complete current source/migration chain.
2. Real LoongArch/Kylin hardware acceptance is absent.
3. Target wheelhouse/checksum manifest has not been produced and verified here.
4. Native PostgreSQL/Nginx/systemd install and restart behavior is untested.
5. Backup/restore and schema rollback are not proven on target.
6. External provider fallback under target networking is untested.

## Allowed Deployment Claim

"The repository contains a native LoongArch/Kylin deployment preparation path using Python venv, PostgreSQL, systemd and Nginx without formal Docker dependence. Real-machine acceptance remains blocked."

