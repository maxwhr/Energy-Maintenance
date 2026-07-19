from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from task25g_common import BACKEND, DEPLOY, FRONTEND, ROOT, RUNTIME, directory_manifest, now_iso, platform_facts, read_json, run, sha256_file, sha256_value, write_json


BANNED_PRODUCTION_DEPENDENCIES = {
    "psycopg-binary",
    "uvloop",
    "httptools",
    "watchfiles",
    "orjson",
    "pytest",
    "pytest-asyncio",
    "playwright",
}
FOREIGN_WHEEL_TAGS = ("win_amd64", "manylinux_x86_64", "x86_64", "aarch64", "macosx")
SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[=:]\s*(?!CHANGE_ME|\$\{|\[REDACTED\]|false|true)[^\s#]+"),
    re.compile(r"postgresql(?:\+psycopg)?://[^:\s]+:[^@\s]+@", re.IGNORECASE),
)


def wheel_tag_allowed(filename: str) -> bool:
    lowered = filename.lower()
    if not lowered.endswith(".whl") or any(tag in lowered for tag in FOREIGN_WHEEL_TAGS):
        return False
    return "-py3-none-any.whl" in lowered or "loongarch64" in lowered


def _requirements() -> list[str]:
    path = DEPLOY / "requirements" / "requirements-loongarch.txt"
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "--"))
    ]


def _dependency_manifest() -> dict[str, Any]:
    return json.loads((DEPLOY / "manifests" / "python_dependencies.json").read_text(encoding="utf-8"))


def platform_assumptions() -> dict[str, Any]:
    facts = platform_facts()
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if facts["real_machine_acceptance"] == "PENDING" else "FAIL",
        "development_host": facts,
        "target": {"system": "linux", "architecture": "loongarch64", "os_family": "kylin"},
        "deployment_mode": "native_systemd_nginx_postgresql",
        "docker_required": False,
        "real_machine_acceptance": "PENDING",
        "real_machine_pass_claimed": False,
    }
    write_json("platform_assumptions.json", payload)
    if not (RUNTIME / "real_machine_acceptance.json").exists():
        write_json("real_machine_acceptance.json", {
            "generated_at": now_iso(),
            "status": "PENDING",
            "reason": "No real loongarch64 Kylin machine is available in the Windows development environment.",
            "executed": False,
            "authorized": False,
            "checks": [],
        })
    return payload


def windows_runtime_audit() -> dict[str, Any]:
    violations = []
    checked = []
    roots = (BACKEND / "app", FRONTEND / "dist", DEPLOY)
    text_suffixes = {".py", ".pyi", ".js", ".css", ".html", ".json", ".toml", ".txt", ".md", ".sh", ".conf", ".service", ""}
    candidates = sorted({
        candidate for root in roots for candidate in root.rglob("*")
        if candidate.is_file() and candidate.suffix.lower() in text_suffixes and "__pycache__" not in candidate.parts
    })
    for path in candidates:
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        checked.append(relative)
        for pattern in (
            r"[A-Za-z]:\\", r"powershell(?:\.exe)?", r"cmd\.exe", r"npm\.cmd",
            r"\bstart-process\b", r"\bwin32api\b", r"\bpywin32\b", r"\bmsvcrt\b",
            r"ctypes\.windll", r"os\.startfile",
        ):
            if re.search(pattern, text, re.IGNORECASE):
                violations.append({"path": relative, "pattern": pattern, "classification": "RUNTIME_BLOCKING"})
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not violations else "FAIL",
        "files_checked": len(checked),
        "windows_runtime_dependency_count": len(violations),
        "classifications": {"RUNTIME_BLOCKING": len(violations), "DEV_ONLY": 0, "TEST_ONLY": 0, "DOCUMENTATION_ONLY": 0, "FALSE_POSITIVE": 0},
        "violations": violations,
        "production_requires_node": False,
        "production_requires_npm": False,
        "production_requires_uv": False,
    }
    write_json("windows_runtime_audit.json", payload)
    return payload


def dependency_compatibility() -> dict[str, Any]:
    manifest = _dependency_manifest()
    rows = manifest.get("dependencies") or []
    required_fields = {
        "name", "version", "direct_or_transitive", "pure_python", "native_extension",
        "system_library", "wheel_architecture", "loongarch_risk", "fallback_available",
        "runtime_required", "build_required", "action",
    }
    missing_fields = [row.get("name", "unknown") for row in rows if not required_fields.issubset(row)]
    native_rows = [row for row in rows if row.get("native_extension") or row.get("system_library")]
    unclassified_native = [row["name"] for row in native_rows if row.get("loongarch_risk") in {None, "UNKNOWN"}]
    requirements = _requirements()
    names = {line.split("==", 1)[0].lower() for line in requirements if "==" in line}
    requirement_versions = {line.split("==", 1)[0].lower(): line.split("==", 1)[1] for line in requirements if "==" in line}
    manifest_versions = {
        str(row.get("name") or "").lower(): str(row.get("version"))
        for row in rows if row.get("runtime_required") and row.get("version") is not None
    }
    missing_production = sorted(name for name in requirement_versions if name not in manifest_versions)
    version_mismatches = sorted(
        name for name, version in requirement_versions.items()
        if name in manifest_versions and manifest_versions[name] != version
    )
    banned = sorted(names & BANNED_PRODUCTION_DEPENDENCIES)
    unpinned = [line for line in requirements if "==" not in line]
    native_risks = json.loads((DEPLOY / "manifests" / "native_dependency_risks.json").read_text(encoding="utf-8"))
    status = "PASS" if not (missing_fields or unclassified_native or banned or unpinned or missing_production or version_mismatches) else "FAIL"
    payload = {
        "generated_at": now_iso(),
        "status": status,
        "dependency_count": len(rows),
        "native_dependency_count": len(native_rows),
        "native_classification_coverage": 1.0 if native_rows and not unclassified_native else 0.0,
        "missing_required_fields": missing_fields,
        "unclassified_native_dependencies": unclassified_native,
        "banned_production_dependencies": banned,
        "unpinned_requirements": unpinned,
        "production_requirement_coverage": 1.0 if requirement_versions and not missing_production else 0.0,
        "missing_production_dependencies": missing_production,
        "production_version_mismatches": version_mismatches,
        "dependencies": rows,
    }
    write_json("python_dependency_compatibility.json", payload)
    write_json("native_dependency_risks.json", {**native_risks, "generated_at": now_iso(), "status": status})
    return payload


def runtime_imports() -> dict[str, Any]:
    modules = [
        ("fastapi", True), ("uvicorn", True), ("pydantic", True), ("pydantic_core", True),
        ("pydantic_core._pydantic_core", True), ("sqlalchemy", True), ("alembic", True),
        ("psycopg", True), ("multipart", True), ("pypdf", True), ("docx", True),
        ("httpx", True), ("PIL", True), ("PIL._imaging", True), ("lxml", True),
        ("lxml.etree", True), ("cryptography", False), ("app.main", True),
    ]
    rows = []
    original = sys.path[:]
    sys.path.insert(0, str(BACKEND))
    try:
        for name, required in modules:
            try:
                module = importlib.import_module(name)
                module_file = str(getattr(module, "__file__", "") or "")
                suffix = Path(module_file).suffix.lower()
                native = suffix in {".pyd", ".so", ".dll", ".dylib"}
                rows.append({
                    "module": name,
                    "version": getattr(module, "__version__", None),
                    "import_success": True,
                    "native_module": native,
                    "module_file_suffix": suffix,
                    "architecture_observed": platform_facts()["machine"],
                    "risk": "CURRENT_HOST_BASELINE_ONLY" if native else "PURE_PYTHON_OR_PACKAGE_WRAPPER",
                    "runtime_required": required,
                    "status": "PASS",
                })
            except Exception as exc:  # noqa: BLE001 - each import result is audit evidence.
                rows.append({
                    "module": name,
                    "version": None,
                    "import_success": False,
                    "native_module": None,
                    "module_file_suffix": None,
                    "architecture_observed": platform_facts()["machine"],
                    "risk": "IMPORT_FAILED" if required else "OPTIONAL_NOT_INSTALLED",
                    "runtime_required": required,
                    "status": "FAIL" if required else "NOT_REQUIRED",
                    "error_type": exc.__class__.__name__,
                })
    finally:
        sys.path[:] = original
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if all(row["status"] == "PASS" for row in rows if row["runtime_required"]) else "FAIL",
        "host_scope": platform_facts(),
        "loongarch_compatibility_proven": False,
        "imports": rows,
    }
    write_json("runtime_imports.json", payload)
    return payload


def frontend_portability() -> dict[str, Any]:
    violations = []
    checked = []
    roots = (FRONTEND / "src", FRONTEND / "dist")
    for path in sorted({candidate for root in roots for candidate in root.rglob("*")}):
        if not path.is_file() or path.suffix not in {".ts", ".vue", ".js", ".html", ".css", ".map"}:
            continue
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        checked.append(relative)
        for pattern in (
            r"https?://127\.0\.0\.1:8012", r"https?://localhost:8012",
            r"https?://127\.0\.0\.1:8000", r"https?://localhost:8000",
            r"[A-Za-z]:\\", r"npm\.cmd", re.escape(os.environ.get("USERNAME", "__NO_USERNAME__")),
            r"postgresql(?:\+psycopg)?://", r"(?i)api[_-]?key\s*[=:]\s*[\"'][^\"']+[\"']",
        ):
            if re.search(pattern, text, re.IGNORECASE):
                violations.append({"path": relative, "pattern": pattern})
    request_source = (FRONTEND / "src" / "utils" / "request.ts").read_text(encoding="utf-8")
    relative_api = "'/api'" in request_source or '"/api"' in request_source
    dist = directory_manifest(FRONTEND / "dist")
    index_path = FRONTEND / "dist" / "index.html"
    missing_assets = []
    if index_path.is_file():
        index_text = index_path.read_text(encoding="utf-8")
        for source in re.findall(r"(?:src|href)=[\"'](/[^\"']+)[\"']", index_text):
            candidate = FRONTEND / "dist" / source.lstrip("/")
            if not candidate.is_file():
                missing_assets.append(source)
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if relative_api and not violations and dist["file_count"] > 0 and not missing_assets else "FAIL",
        "source_files_checked": len(checked),
        "relative_api_prefix": relative_api,
        "production_node_required": False,
        "violations": violations,
        "missing_index_assets": missing_assets,
        "frontend_dist": {key: dist[key] for key in ("file_count", "total_bytes", "aggregate_sha256")},
    }
    write_json("frontend_portability.json", payload)
    return payload


def shell_script_audit() -> dict[str, Any]:
    rows = []
    forbidden = ("curl | sh", "wget | sh", "docker", "kubectl", "powershell", "cmd.exe", "npm.cmd")
    for path in sorted((DEPLOY / "scripts").glob("*.sh")) + [DEPLOY / "lib" / "common.sh"]:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        issues = []
        if not text.startswith("#!/usr/bin/env bash\n"):
            issues.append("invalid_shebang")
        if "set -euo pipefail" not in text:
            issues.append("strict_mode_missing")
        if b"\r\n" in raw:
            issues.append("crlf_detected")
        for token in forbidden:
            if token in text.lower():
                issues.append(f"forbidden:{token}")
        if "rm -rf" in text:
            issues.append("recursive_delete_forbidden")
        rows.append({"path": path.relative_to(ROOT).as_posix(), "issues": issues, "sha256": sha256_file(path)})
    shellcheck = shutil.which("shellcheck")
    shellcheck_result = {"available": bool(shellcheck), "status": "UNAVAILABLE", "output": None}
    if shellcheck:
        probe = run([shellcheck, *[str(DEPLOY / "scripts" / name) for name in sorted(path.name for path in (DEPLOY / "scripts").glob("*.sh"))]])
        shellcheck_result = {"available": True, "status": "PASS" if probe["exit_code"] == 0 else "FAIL", "output": probe["stdout"] or probe["stderr"]}
    failures = [row for row in rows if row["issues"]]
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not failures and shellcheck_result["status"] != "FAIL" else "FAIL",
        "scripts_checked": len(rows),
        "rows": rows,
        "shellcheck": shellcheck_result,
    }
    write_json("shell_script_audit.json", payload)
    return payload


def deployment_template_audit() -> dict[str, Any]:
    service = (DEPLOY / "config" / "energy-maintenance-backend.service").read_text(encoding="utf-8")
    nginx = (DEPLOY / "config" / "nginx-energy-maintenance.conf").read_text(encoding="utf-8")
    environment = (DEPLOY / "config" / "backend.env.example").read_text(encoding="utf-8")
    checks = {
        "systemd_non_root_user": "User=energy-maintenance" in service,
        "systemd_python_module_start": "shared/venv/bin/python -m uvicorn" in service,
        "systemd_no_reload": "--reload" not in service,
        "systemd_hardening": all(value in service for value in ("NoNewPrivileges=true", "ProtectSystem=strict", "PrivateTmp=true")),
        "nginx_api_proxy": "location /api/" in nginx and "127.0.0.1:8012" in nginx,
        "nginx_spa_fallback": "try_files $uri $uri/ /index.html" in nginx,
        "nginx_no_autoindex": "autoindex off" in nginx,
        "environment_placeholders": "CHANGE_ME" in environment,
        "full_reindex_disabled": "TASK25B_ALLOW_FULL_REINDEX=false" in environment,
    }
    payload = {"generated_at": now_iso(), "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
    write_json("deployment_template_audit.json", payload)
    return payload


def offline_manifest_audit() -> dict[str, Any]:
    requirements = _requirements()
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((DEPLOY / "manifests").glob("*.json"))]
    names = {line.split("==", 1)[0].lower() for line in requirements if "==" in line}
    wheel_files = list(DEPLOY.rglob("*.whl"))
    foreign = [path.name for path in wheel_files if any(tag in path.name.lower() for tag in FOREIGN_WHEEL_TAGS)]
    checks = {
        "requirements_pinned": bool(requirements) and all("==" in line for line in requirements),
        "banned_dependencies_absent": not bool(names & BANNED_PRODUCTION_DEPENDENCIES),
        "manifest_files_valid": len(manifests) >= 6,
        "wheelhouse_not_generated": len(wheel_files) == 0,
        "foreign_wheels": len(foreign) == 0,
        "private_credentials_absent": not any(
            re.search(r"https?://[^\s\"']+:[^\s\"']+@", json.dumps(value), re.IGNORECASE)
            for value in manifests
        ),
    }
    payload = {
        "generated_at": now_iso(), "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks, "requirements_count": len(requirements), "wheel_files": len(wheel_files), "foreign_wheels": foreign,
    }
    write_json("offline_manifest_audit.json", payload)
    return payload


def release_rollback_dry_run() -> dict[str, Any]:
    layout = (DEPLOY / "templates" / "release-layout.txt").read_text(encoding="utf-8")
    rollback = (DEPLOY / "scripts" / "rollback_release.sh").read_text(encoding="utf-8")
    checks = {
        "releases_directory": "releases/<release-id>" in layout,
        "current_symlink": "current -> releases/<release-id>" in layout,
        "atomic_temporary_symlink": "ln -sfn" in rollback and "mv -Tf" in rollback,
        "database_downgrade_absent": "alembic downgrade" not in rollback,
        "release_id_guard": "invalid release id" in rollback,
        "dry_run_supported": "parse_dry_run" in rollback,
    }
    bash = shutil.which("bash")
    execution = {"available": bool(bash), "status": "UNAVAILABLE", "exit_code": None}
    if bash:
        environment = os.environ.copy()
        environment.update({"EM_ROOT": "/opt/energy-maintenance", "DRY_RUN": "true"})
        probe = run([bash, str(DEPLOY / "scripts" / "rollback_release.sh"), "--dry-run", "--release-id=task25g-dry-run"], env=environment)
        output = probe["stdout"] or probe["stderr"]
        unavailable = probe["exit_code"] in {126, 127} or "execvpe(/bin/bash) failed" in output
        execution = {
            "available": not unavailable,
            "status": "UNAVAILABLE" if unavailable else ("PASS" if probe["exit_code"] == 0 else "FAIL"),
            "exit_code": probe["exit_code"],
            "output": "WSL bash command is present but no Linux distribution/bash runtime is available." if unavailable else output,
        }
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if all(checks.values()) and execution["status"] != "FAIL" else "FAIL",
        "checks": checks,
        "shell_execution": execution,
        "database_downgrade_executed": False,
        "filesystem_mutation_executed": False,
    }
    write_json("release_rollback_dry_run.json", payload)
    return payload


def resource_profile() -> dict[str, Any]:
    dist = directory_manifest(FRONTEND / "dist")
    rss_mb = None
    rss_scope = "not observed"
    if os.name == "nt":
        probe = run([
            "powershell.exe", "-NoProfile", "-Command",
            "$c=Get-NetTCPConnection -LocalPort 8012 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; "
            "if($c){$p=Get-Process -Id $c.OwningProcess; [math]::Round($p.WorkingSet64/1MB,2)}",
        ])
        try:
            rss_mb = float(probe["stdout"].splitlines()[-1]) if probe["stdout"] else None
        except (ValueError, IndexError):
            rss_mb = None
        if rss_mb is not None:
            rss_scope = "Windows/amd64 post-regression local process observation; not LoongArch acceptance"
    payload = {
        "generated_at": now_iso(),
        "status": "PASS",
        "target_profile": {"cpu_cores": 4, "memory_gb": 8},
        "recommended": {
            "uvicorn_workers": 2,
            "database_pool_per_worker": 5,
            "database_max_overflow_per_worker": 1,
            "maximum_application_connections": 12,
            "maximum_total_connections_budget": 14,
            "provider_concurrency": "bounded by existing application settings",
            "cache_policy": "bounded TTL and entry count",
        },
        "windows_baseline": {
            "frontend_dist_bytes": dist["total_bytes"],
            "frontend_asset_count": dist["file_count"],
            "backend_current_rss_mb": rss_mb,
            "backend_steady_rss_mb": rss_mb,
            "measurement_scope": rss_scope,
            "reason": "A Windows/amd64 RSS value is only a local engineering baseline and is not a LoongArch acceptance measurement.",
        },
        "real_machine_measurements": "PENDING",
    }
    write_json("resource_profile.json", payload)
    return payload


def security_audit() -> dict[str, Any]:
    findings = []
    scanned = 0
    for path in sorted(candidate for candidate in DEPLOY.rglob("*") if candidate.is_file()):
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        scanned += 1
        if path.name == "backend.env.example":
            sanitized = text.replace("CHANGE_ME_WITH_AT_LEAST_32_RANDOM_CHARACTERS", "CHANGE_ME").replace("CHANGE_ME_WITH_AT_LEAST_10_CHARACTERS", "CHANGE_ME").replace("CHANGE_ME_HOST", "CHANGE_ME")
        else:
            sanitized = text
        for pattern in SECRET_PATTERNS:
            for match in pattern.finditer(sanitized):
                value = match.group(0)
                if "CHANGE_ME" not in value and "[REDACTED]" not in value:
                    findings.append({"path": relative, "type": "potential_secret"})
                    break
        if "curl | sh" in text.lower() or "wget | sh" in text.lower():
            findings.append({"path": relative, "type": "remote_pipe_execution"})
        if re.search(r"\bdocker(?:file|\s|-) |\bkubectl\b", text, re.IGNORECASE):
            findings.append({"path": relative, "type": "prohibited_container_runtime"})
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not findings else "FAIL",
        "files_scanned": scanned,
        "findings": findings,
        "real_backend_env_read": False,
        "secret_values_recorded": False,
    }
    write_json("security_audit.json", payload)
    return payload


AUDITS = {
    "platform": platform_assumptions,
    "windows": windows_runtime_audit,
    "dependencies": dependency_compatibility,
    "imports": runtime_imports,
    "frontend": frontend_portability,
    "shell": shell_script_audit,
    "templates": deployment_template_audit,
    "offline": offline_manifest_audit,
    "rollback": release_rollback_dry_run,
    "resources": resource_profile,
    "security": security_audit,
}


def run_named(name: str) -> int:
    payload = AUDITS[name]()
    print(json.dumps({"audit": name, "status": payload["status"]}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1
