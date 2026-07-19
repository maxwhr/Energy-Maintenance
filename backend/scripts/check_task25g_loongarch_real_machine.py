from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from task25g_common import BACKEND, EXPECTED_ALEMBIC_REVISION, EXPECTED_MACHINE, RUNTIME, now_iso, write_json

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _os_release() -> str:
    path = Path("/etc/os-release")
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def validate_real_machine_guard(*, allow: bool) -> tuple[bool, list[str]]:
    reasons = []
    if platform.system().lower() != "linux":
        reasons.append("system_is_not_linux")
    if platform.machine().lower() != EXPECTED_MACHINE:
        reasons.append("architecture_is_not_loongarch64")
    if "kylin" not in _os_release().lower():
        reasons.append("os_is_not_kylin")
    if not allow:
        reasons.append("explicit_authorization_missing")
    return not reasons, reasons


def _command(name: str, command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=120)
    return {"name": name, "status": "PASS" if completed.returncode == 0 else "FAIL", "exit_code": completed.returncode}


def _request(url: str, *, method: str = "GET", token: str | None = None, payload: dict | None = None) -> dict:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - target is guard-restricted local acceptance URL.
            value = json.loads(response.read().decode("utf-8"))
        return {"status": "PASS" if value.get("code") == 200 else "FAIL", "http_status": response.status, "data": value.get("data")}
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return {"status": "FAIL", "error_type": exc.__class__.__name__}


def _plain_http(url: str) -> dict:
    try:
        with urlopen(Request(url, headers={"Accept": "text/html"}), timeout=30) as response:  # noqa: S310 - local target after platform guard.
            content_type = response.headers.get("Content-Type", "")
            body = response.read(4096)
        return {"status": "PASS" if response.status == 200 and b"<html" in body.lower() else "FAIL", "http_status": response.status, "content_type": content_type}
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"status": "FAIL", "error_type": exc.__class__.__name__}


def _automatic_checks(base_url: str) -> tuple[list[dict], str | None]:
    if base_url not in {"http://127.0.0.1:8012", "http://localhost:8012"}:
        raise RuntimeError("real-machine acceptance backend URL must remain local")
    checks = []
    for module_name in ("fastapi", "uvicorn", "pydantic_core._pydantic_core", "sqlalchemy", "alembic", "psycopg", "PIL._imaging", "lxml.etree", "app.main"):
        try:
            importlib.import_module(module_name)
            checks.append({"name": f"import:{module_name}", "status": "PASS"})
        except Exception as exc:  # noqa: BLE001 - real-machine evidence needs per-module result.
            checks.append({"name": f"import:{module_name}", "status": "FAIL", "error_type": exc.__class__.__name__})
    checks.extend([
        _command("systemd_active", ["systemctl", "is-active", "--quiet", "energy-maintenance-backend.service"]),
        _command("nginx_config", ["nginx", "-t"]),
    ])
    alembic = subprocess.run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=120)
    checks.append({"name": "alembic_current", "status": "PASS" if alembic.returncode == 0 and EXPECTED_ALEMBIC_REVISION in alembic.stdout else "FAIL", "exit_code": alembic.returncode, "expected_revision": EXPECTED_ALEMBIC_REVISION})
    from sqlalchemy import text
    from app.core.database import SessionLocal
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        checks.append({"name": "postgresql_select_1", "status": "PASS"})
    except Exception as exc:  # noqa: BLE001
        checks.append({"name": "postgresql_select_1", "status": "FAIL", "error_type": exc.__class__.__name__})
    health = _request(f"{base_url}/api/health")
    checks.append({"name": "backend_health", **{key: value for key, value in health.items() if key != "data"}})
    checks.append({"name": "nginx_frontend", **_plain_http("http://127.0.0.1/")})

    username = os.environ.get("TASK25G_ACCEPTANCE_USERNAME", "")
    password = os.environ.get("TASK25G_ACCEPTANCE_PASSWORD", "")
    token = None
    if username and password:
        login = _request(f"{base_url}/api/auth/login", method="POST", payload={"username": username, "password": password})
        login_data = login.pop("data", None) or {}
        token = login_data.get("access_token") or login_data.get("token")
        checks.append({"name": "login", **login, "token_exposed": False})
    else:
        checks.append({"name": "login", "status": "FAIL", "reason": "acceptance credentials were not provided"})
    if token:
        api_checks = {
            "knowledge_search": ("GET", "/api/knowledge/documents?page=1&page_size=1", None),
            "record_center": ("GET", "/api/records/qa?page=1&page_size=1", None),
            "maintenance_workflow": ("GET", "/api/system/maintenance-workflow/status", None),
            "deterministic_rag": ("POST", "/api/retrieval/query", {"question": "SUN2000 设备离线时应先检查什么？", "device_type": "pv_inverter"}),
        }
        for name, (method, path, payload) in api_checks.items():
            result = _request(f"{base_url}{path}", method=method, token=token, payload=payload)
            checks.append({"name": name, **{key: value for key, value in result.items() if key != "data"}})
    cpu = os.cpu_count() or 0
    memory_kb = 0
    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                memory_kb = int(line.split()[1])
                break
    checks.append({"name": "resource_minimum", "status": "PASS" if cpu >= 4 and memory_kb >= 7_500_000 else "FAIL", "cpu_cores": cpu, "memory_kb": memory_kb})
    checks.append({"name": "logrotate_configuration", "status": "PASS" if Path("/etc/logrotate.d/energy-maintenance").is_file() else "FAIL"})
    return checks, token


def _manual_checks(path: Path | None) -> list[dict]:
    required = (
        "image_upload", "ocr_safe_fallback", "systemd_restart", "os_reboot_recovery",
        "backup_restore", "release_rollback", "four_core_eight_gb_profile",
        "concurrency", "long_running_stability",
    )
    evidence = {}
    if path and path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
        evidence = value if isinstance(value, dict) else {}
    return [
        {"name": f"manual:{name}", "status": "PASS" if (evidence.get(name) or {}).get("status") == "PASS" else "PENDING", "evidence_id": (evidence.get(name) or {}).get("evidence_id")}
        for name in required
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-machine-acceptance", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8012")
    parser.add_argument("--manual-evidence", type=Path)
    args = parser.parse_args()
    accepted, reasons = validate_real_machine_guard(allow=args.allow_real_machine_acceptance)
    if not accepted:
        print(json.dumps({"status": "PENDING", "executed": False, "reasons": reasons}))
        return 3
    automatic, _token = _automatic_checks(args.base_url)
    manual = _manual_checks(args.manual_evidence)
    checks = automatic + manual
    complete = all(item["status"] == "PASS" for item in checks)
    payload = {
        "generated_at": now_iso(),
        "status": "TASK25G_LOONGARCH_KYLIN_REAL_MACHINE_PASS" if complete else "REAL_MACHINE_ACCEPTANCE_INCOMPLETE",
        "executed": True,
        "authorized": True,
        "platform": {"system": platform.system().lower(), "architecture": platform.machine().lower(), "os_family": "kylin"},
        "checks": checks,
        "credentials_exposed": False,
        "real_external_provider_calls": False,
        "note": "A final pass requires every automatic and manual-evidence check to pass.",
    }
    write_json(RUNTIME / "real_machine_acceptance.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
