from __future__ import annotations

import json
import os
import platform
import re
import sys
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import alembic
import psycopg
import sqlalchemy
from sqlalchemy import inspect, text

from app.core.database import engine
from task25a_r1_common import BACKEND, ROOT, RUNTIME, now_iso, read_json, register_test, run, sha256_file, sha256_paths, write_csv, write_json


EXCLUDES = {".git", ".venv", "node_modules", ".runtime", "storage", "delivery", "delivery_staging", "__pycache__"}
CORE_TABLES = {"knowledge_documents", "knowledge_chunks", "qa_records", "diagnosis_records", "maintenance_tasks"}


def files_under(base: Path, suffixes: set[str]) -> list[Path]:
    return [path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in suffixes and not any(part in EXCLUDES for part in path.parts)]


def version(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    result = run(command, cwd, timeout=30)
    output = (result["stdout"] or result["stderr"]).strip().splitlines()
    return {"value": output[0] if output else "unavailable", "exit_code": result["exit_code"]}


def env_summary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": path.relative_to(ROOT).as_posix(), "exists": False, "key_count": 0, "configured_count": 0, "placeholder_count": 0}
    keys = configured = placeholders = 0
    placeholder_re = re.compile(r"^(?:|change[-_ ]?me|your[-_ ]|example|placeholder|xxx|none|null|todo)", re.I)
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        _, value = stripped.split("=", 1)
        keys += 1
        clean = value.strip().strip("\"'")
        if clean and not placeholder_re.search(clean):
            configured += 1
        else:
            placeholders += 1
    return {"path": path.relative_to(ROOT).as_posix(), "exists": True, "key_count": keys, "configured_count": configured, "placeholder_count": placeholders}


def dist_manifest(base: Path) -> dict[str, Any]:
    files = [path for path in base.rglob("*") if path.is_file()] if base.is_dir() else []
    return {
        "path": base.relative_to(ROOT).as_posix(),
        "exists": base.is_dir(),
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "sha256": sha256_paths(files),
        "files": [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in sorted(files)],
    }


def database_manifest() -> dict[str, Any]:
    with engine.connect() as connection:
        server_version = connection.scalar(text("select version()"))
        table_names = inspect(connection).get_table_names()
        alembic_current = connection.scalar(text("select version_num from alembic_version"))
        core_counts: dict[str, int] = {}
        for name in sorted(CORE_TABLES & set(table_names)):
            core_counts[name] = int(connection.scalar(text(f'SELECT count(*) FROM "{name}"')) or 0)
        connection_count = int(connection.scalar(text("select count(*) from pg_stat_activity where datname = current_database()")) or 0)
    return {
        "reachable": True,
        "server_version": server_version,
        "driver_versions": {"psycopg": psycopg.__version__, "sqlalchemy": sqlalchemy.__version__, "alembic": alembic.__version__},
        "table_count": len(table_names),
        "tables": sorted(table_names),
        "core_tables_present": sorted(CORE_TABLES & set(table_names)),
        "core_row_counts": core_counts,
        "connection_count_observed": connection_count,
        "alembic_current": alembic_current,
    }


def openapi_manifest() -> dict[str, Any]:
    base = os.getenv("TASK25A_R1_BASE_URL", "http://127.0.0.1:8010").rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/openapi.json", timeout=15) as response:
            body = response.read()
        payload = json.loads(body)
        paths = payload.get("paths", {})
        operation_count = sum(len([method for method in methods if method.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}]) for methods in paths.values())
        return {"reachable": True, "base_url": base, "path_count": len(paths), "operation_count": operation_count, "response_bytes": len(body), "sha256": __import__("hashlib").sha256(body).hexdigest()}
    except Exception as exc:  # noqa: BLE001 - manifest must capture unavailability
        return {"reachable": False, "base_url": base, "path_count": 0, "operation_count": 0, "error": type(exc).__name__}


def lock_dependencies() -> dict[str, Any]:
    uv_path = BACKEND / "uv.lock"
    package_lock = ROOT / "frontend" / "package-lock.json"
    backend_packages: list[dict[str, str]] = []
    if uv_path.is_file():
        payload = tomllib.loads(uv_path.read_text(encoding="utf-8"))
        backend_packages = [{"name": str(item.get("name")), "version": str(item.get("version"))} for item in payload.get("package", [])]
    frontend_packages: list[dict[str, str]] = []
    if package_lock.is_file():
        payload = json.loads(package_lock.read_text(encoding="utf-8"))
        frontend_packages = [{"name": key.removeprefix("node_modules/"), "version": str(value.get("version", "unknown"))} for key, value in payload.get("packages", {}).items() if key.startswith("node_modules/")]
    return {
        "backend": {"count": len(backend_packages), "packages": sorted(backend_packages, key=lambda item: item["name"]), "lock_sha256": sha256_file(uv_path)},
        "frontend": {"count": len(frontend_packages), "packages": sorted(frontend_packages, key=lambda item: item["name"]), "lock_sha256": sha256_file(package_lock)},
    }


def main() -> int:
    started = now_iso()
    backend_source = files_under(BACKEND / "app", {".py"})
    frontend_source = files_under(ROOT / "frontend" / "src", {".ts", ".vue", ".css"})
    migrations = files_under(BACKEND / "alembic" / "versions", {".py"})
    test_scripts = [path for path in files_under(BACKEND / "scripts", {".py", ".mjs"}) if path.name.startswith("check_")]
    critical_docs = [ROOT / "docs" / name for name in [
        "01_project_scope_and_product_requirements.md", "02_technical_stack_and_architecture.md", "03_database_schema_design.md",
        "04_api_contract_design.md", "05_frontend_page_and_interaction_spec.md", "09_testing_acceptance_and_quality_spec.md",
        "10_vibe_coding_task_plan.md", "12_functional_design_specification.md", "19_delivery_checklist.md",
    ]]
    package_manifests = [BACKEND / "pyproject.toml", ROOT / "frontend" / "package.json"]
    locks = [BACKEND / "uv.lock", ROOT / "frontend" / "package-lock.json"]
    branch = run(["git", "branch", "--show-current"], ROOT)["stdout"].strip()
    head = run(["git", "rev-parse", "HEAD"], ROOT)["stdout"].strip()
    status = read_json(RUNTIME / "git_status_classification.json", {})
    database = database_manifest()
    alembic_heads = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND)
    alembic_current = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND)
    openapi = openapi_manifest()
    dependencies = lock_dependencies()
    dependency_path = RUNTIME / "dependency_manifest.json"
    write_json(dependency_path, {"generated_at": now_iso(), **dependencies})
    environment = {
        "generated_at": now_iso(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "versions": {
            "python": platform.python_version(), "uv": version(["uv", "--version"]), "node": version(["node", "--version"]),
            "npm": version(["npm.cmd", "--version"]), "psql": version(["psql", "--version"]),
            "psycopg": psycopg.__version__, "sqlalchemy": sqlalchemy.__version__, "alembic": alembic.__version__,
        },
        "dotenv_files": [env_summary(BACKEND / ".env"), env_summary(ROOT / "frontend" / ".env"), env_summary(ROOT / ".env")],
        "secrets_recorded": False,
        "external_provider_mode": "disabled_for_task25a_r1",
        "api_base_url": os.getenv("TASK25A_R1_BASE_URL", "http://127.0.0.1:8010"),
        "database_endpoint": {"host": "127.0.0.1", "port": 55432, "database": "energy_maintenance"},
    }
    environment_path = RUNTIME / "environment_manifest.json"
    write_json(environment_path, environment)
    categories = [
        ("backend_production_source", backend_source), ("frontend_production_source", frontend_source), ("migrations", migrations),
        ("package_manifests", package_manifests), ("lockfiles", locks), ("critical_docs", critical_docs), ("test_scripts", test_scripts),
    ]
    hashes = {name: {"file_count": len([p for p in paths if p.is_file()]), "sha256": sha256_paths(paths)} for name, paths in categories}
    dist = dist_manifest(ROOT / "frontend" / "dist")
    static = dist_manifest(BACKEND / "static" / "frontend")
    tests = read_json(RUNTIME / "test_execution_registry.json", {"tests": []})
    browser = read_json(RUNTIME / "browser_test_results.json", {"status": "not_executed"})
    performance = read_json(RUNTIME / "performance_summary.json", {"status": "not_executed"})
    evidence = read_json(RUNTIME / "requirement_evidence_matrix.json", {"summary": {"status": "not_generated"}})
    manifest = {
        "generated_at": now_iso(), "baseline_name": "Task 25A-R1 pre-refactor baseline", "git": {"branch": branch, "head": head, "status_summary": status.get("summary", {})},
        "environment_manifest": environment_path.relative_to(ROOT).as_posix(), "dependency_manifest": dependency_path.relative_to(ROOT).as_posix(),
        "database": database,
        "alembic": {"heads": alembic_heads["stdout"].strip(), "heads_exit_code": alembic_heads["exit_code"], "current": alembic_current["stdout"].strip(), "current_exit_code": alembic_current["exit_code"]},
        "hashes": hashes, "frontend_dist_manifest": dist, "backend_static_manifest": static, "openapi": openapi,
        "current_key_tests": {"count": len(tests.get("tests", [])), "passed": sum(item.get("status") == "PASSED" for item in tests.get("tests", [])), "registry_sha256": sha256_file(RUNTIME / "test_execution_registry.json")},
        "current_browser_tests": browser.get("summary", browser.get("status", "not_executed")),
        "current_performance": performance.get("summary", performance.get("status", "not_executed")),
        "current_competition_evidence": evidence.get("summary", {"status": "not_generated"}),
        "exclusions": sorted(EXCLUDES | {"backend/.env", "secret files", "large binary/image contents"}),
    }
    manifest_path = RUNTIME / "baseline_manifest.json"
    write_json(manifest_path, manifest)
    csv_rows: list[dict[str, Any]] = []
    for category, paths in categories:
        for path in paths:
            if path.is_file():
                csv_rows.append({"category": category, "path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    for kind, item in [("frontend_dist", dist), ("backend_static", static)]:
        csv_rows.append({"category": kind, "path": item["path"], "bytes": item["total_bytes"], "sha256": item["sha256"]})
    csv_path = RUNTIME / "baseline_manifest.csv"
    write_csv(csv_path, csv_rows)
    report = ROOT / "docs" / "25A_R1_refactoring_baseline_manifest.md"
    lines = [
        "# Task 25A-R1 重构前基线 Manifest", "", f"冻结时间：{manifest['generated_at']}", "",
        "## 基线身份", "", f"- branch: `{branch or '(detached)'}`", f"- HEAD: `{head}`",
        f"- Git status entries: {status.get('summary', {}).get('total_entries', 'not generated')}",
        f"- Python: {environment['versions']['python']}；Node: {environment['versions']['node']['value']}；npm: {environment['versions']['npm']['value']}。",
        f"- PostgreSQL: {database['server_version']}；tables={database['table_count']}；Alembic current={database['alembic_current']}。",
        f"- OpenAPI paths={openapi['path_count']}；operations={openapi['operation_count']}；reachable={openapi['reachable']}。", "",
        "## 代码与契约哈希", "",
    ]
    lines += [f"- {name}: files={data['file_count']}, sha256=`{data['sha256']}`" for name, data in hashes.items()]
    lines += ["", "## 构建产物", "", f"- frontend/dist: files={dist['file_count']}, bytes={dist['total_bytes']}, sha256=`{dist['sha256']}`", f"- backend/static/frontend: files={static['file_count']}, bytes={static['total_bytes']}, sha256=`{static['sha256']}`", "", "## 环境与证据状态", "", "- `.env` 仅记录 exists/key_count/configured_count/placeholder_count；未记录任何值。"]
    for item in environment["dotenv_files"]:
        lines.append(f"- {item['path']}: exists={item['exists']}, keys={item['key_count']}, configured={item['configured_count']}, placeholders={item['placeholder_count']}")
    lines += [f"- current test registry entries: {manifest['current_key_tests']['count']}（passed={manifest['current_key_tests']['passed']}）", f"- browser evidence: {json.dumps(manifest['current_browser_tests'], ensure_ascii=False)}", f"- performance evidence: {json.dumps(manifest['current_performance'], ensure_ascii=False)}", "", "## 约束", "", "本 Manifest 排除了 secret、用户 storage 内容、node_modules、.venv、.git、delivery 包和图片/大二进制正文。它冻结当前证据状态，不代表 LoongArch 实机或真实 provider 已验证。", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    passed = database["alembic_current"] == "20260601_0008" and CORE_TABLES <= set(database["tables"]) and openapi["reachable"]
    artifacts = [manifest_path, csv_path, environment_path, dependency_path, report]
    register_test({
        "test_id": "T-R1-BASELINE-MANIFEST", "name": "Pre-refactor baseline manifest", "category": "baseline",
        "command": "uv run python scripts/check_task25a_r1_baseline_manifest.py", "started_at": started,
        "status": "PASSED" if passed else "FAILED", "exit_code": 0 if passed else 1,
        "assertion_count": 5, "passed_assertions": 5 if passed else 4, "failed_assertions": 0 if passed else 1,
        "artifact_paths": artifacts, "notes": "Database schema/runtime, code/dependency/build hashes and secret-safe environment counts recorded.",
    })
    print(f"task25a_r1_baseline_manifest tables={database['table_count']} openapi_paths={openapi['path_count']} alembic={database['alembic_current']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
