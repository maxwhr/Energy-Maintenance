from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from task25f_common import now_iso, read_json, sha256_file, write_json


def execute(name: str, command: list[str], cwd: Path, timeout: int = 900) -> dict:
    started = perf_counter()
    env = os.environ.copy()
    env["TASK25B_ALLOW_FULL_REINDEX"] = "false"
    env.update({
        "BASE_URL": "http://127.0.0.1:8012",
        "GLOBAL_ACCEPTANCE_API_BASE_URL": "http://127.0.0.1:8012/api",
        "MULTIMODAL_EVIDENCE_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK22G_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK22H_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK22I_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK22J_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK24E_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK25D_BASE_URL": "http://127.0.0.1:8012",
        "TASK25E_BASE_URL": "http://127.0.0.1:8012",
    })
    completed = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout, check=False,
    )
    output = "\n".join(value for value in (completed.stdout.strip(), completed.stderr.strip()) if value)
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    version_line = next((line for line in lines if "20260712_0015" in line), None)
    evidence_line = (version_line or (lines[-1] if lines else ""))[:500]
    record = {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "duration_ms": round((perf_counter() - started) * 1000, 3),
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
        "last_line": evidence_line,
        "full_output_recorded": False,
    }
    print(json.dumps({"name": name, "status": record["status"], "duration_ms": record["duration_ms"], "last_line": evidence_line}, ensure_ascii=False), flush=True)
    return record


def frozen_status_record(name: str, key: str) -> dict:
    baseline = read_json("baseline.json", {})
    evidence = (baseline.get("frozen_evidence") or {}).get(key) or {}
    target = ROOT / str(evidence.get("path") or "")
    expected = evidence.get("sha256")
    current = sha256_file(target) if target.is_file() else None
    passed = bool(expected) and current == expected
    return {
        "name": name,
        "command": ["read-only-frozen-evidence-verification", str(evidence.get("path") or "")],
        "cwd": str(ROOT),
        "exit_code": 0 if passed else 1,
        "status": "PASS" if passed else "FAIL",
        "duration_ms": 0.0,
        "output_sha256": current,
        "last_line": "frozen status evidence unchanged" if passed else "frozen status evidence mismatch",
        "full_output_recorded": False,
    }


def main() -> int:
    failed_only = "--failed-only" in sys.argv
    refresh_core = "--refresh-core" in sys.argv
    commands = [
        ("compileall", ["uv", "run", "python", "-m", "compileall", "app", "scripts", "tests"], BACKEND, 600),
        ("alembic_heads", ["uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND, 120),
        ("alembic_current", ["uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND, 120),
        ("pytest", ["uv", "run", "--extra", "dev", "pytest", "-q"], BACKEND, 1200),
        ("security_config", ["uv", "run", "python", "scripts/check_security_config_status.py"], BACKEND, 180),
        ("secret_leak_scan", ["uv", "run", "python", "scripts/check_secret_leak_scan.py"], BACKEND, 300),
        ("log_sanitization", ["uv", "run", "python", "scripts/check_log_sanitization.py"], BACKEND, 180),
        ("upload_security", ["uv", "run", "python", "scripts/check_upload_security.py"], BACKEND, 180),
        ("rbac_matrix", ["uv", "run", "python", "scripts/check_rbac_security_matrix.py"], BACKEND, 300),
        ("regression_fixture_cleanup", ["uv", "run", "python", "scripts/cleanup_task25f_regression_fixtures.py"], BACKEND, 180),
        ("dashvector_hybrid_rag_flow", ["uv", "run", "python", "scripts/check_dashvector_hybrid_rag_flow.py"], BACKEND, 300),
        ("multimodal_evidence_flow", ["uv", "run", "python", "scripts/check_multimodal_evidence_flow.py"], BACKEND, 300),
        ("multimodal_evidence_agent_flow", ["uv", "run", "python", "scripts/check_multimodal_evidence_agent_flow.py"], BACKEND, 300),
        ("diagnosis_sop_task_agent_flow", ["uv", "run", "python", "scripts/check_diagnosis_sop_task_agent_flow.py"], BACKEND, 300),
        ("knowledge_curator_agent_flow", ["uv", "run", "python", "scripts/check_knowledge_curator_agent_flow.py"], BACKEND, 300),
        ("agent_artifact_conversion_flow", ["uv", "run", "python", "scripts/check_agent_artifact_conversion_flow.py"], BACKEND, 300),
        ("agent_conversion_concurrency_flow", ["uv", "run", "python", "scripts/check_agent_conversion_concurrency_flow.py"], BACKEND, 300),
        ("npm_install", ["npm.cmd", "install"], FRONTEND, 600),
        ("npm_audit", ["npm.cmd", "audit"], FRONTEND, 300),
        ("frontend_build", ["npm.cmd", "run", "build"], FRONTEND, 600),
        ("vue_tsc", ["npx.cmd", "vue-tsc", "--noEmit"], FRONTEND, 600),
        ("static_frontend_install", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BACKEND / "scripts" / "build_and_install_frontend.ps1")], ROOT, 600),
        ("browser", ["node", "backend/scripts/check_task25f_browser.mjs"], ROOT, 600),
        ("final_smoke", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "final_smoke_test.ps1"), "-BaseUrl", "http://127.0.0.1:8012"], ROOT, 600),
    ]
    previous = read_json("regression.json", {}) if failed_only else {}
    if refresh_core:
        previous = read_json("regression.json", {})
    previous_records = {item["name"]: item for item in previous.get("commands", [])}
    if failed_only:
        retry_names = {name for name, item in previous_records.items() if item.get("status") != "PASS"}
        if (previous.get("groups") or {}).get("alembic") != "PASS":
            retry_names.update({"alembic_heads", "alembic_current"})
        missing_names = {item[0] for item in commands if item[0] not in previous_records}
        commands = [item for item in commands if item[0] in retry_names | missing_names]
    elif refresh_core:
        core_names = {
            "compileall", "alembic_heads", "alembic_current", "pytest",
            "browser", "final_smoke",
        }
        commands = [item for item in commands if item[0] in core_names]
    records_by_name = dict(previous_records)
    for name, command, cwd, timeout in commands:
        try:
            record = execute(name, command, cwd, timeout)
        except subprocess.TimeoutExpired:
            record = {
                "name": name, "command": command, "cwd": str(cwd), "exit_code": None,
                "status": "TIMEOUT", "duration_ms": timeout * 1000, "output_sha256": None,
                "last_line": "command timeout", "full_output_recorded": False,
            }
        records_by_name[name] = record
        write_json("regression.json", {
            "generated_at": now_iso(), "status": "RUNNING", "commands": list(records_by_name.values()),
        })

    records_by_name["task25d_regression"] = frozen_status_record(
        "task25d_regression", "task25d_report"
    )
    records_by_name["task25e_regression"] = frozen_status_record(
        "task25e_regression", "task25e_result"
    )
    records = list(records_by_name.values())

    by_name = {item["name"]: item for item in records}
    heads_ok = by_name["alembic_heads"]["status"] == "PASS" and "20260712_0015" in by_name["alembic_heads"]["last_line"]
    current_ok = by_name["alembic_current"]["status"] == "PASS" and "20260712_0015" in by_name["alembic_current"]["last_line"]
    passed = all(item["status"] == "PASS" for item in records) and heads_ok and current_ok
    groups = {
        "compileall": by_name["compileall"]["status"],
        "alembic": "PASS" if heads_ok and current_ok else "FAIL",
        "pytest": by_name["pytest"]["status"],
        "security": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("security_config", "secret_leak_scan", "log_sanitization", "upload_security")) else "FAIL",
        "rbac": by_name["rbac_matrix"]["status"],
        "rag_flow": by_name["dashvector_hybrid_rag_flow"]["status"],
        "agents": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("multimodal_evidence_agent_flow", "diagnosis_sop_task_agent_flow", "knowledge_curator_agent_flow")) else "FAIL",
        "conversion": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("agent_artifact_conversion_flow", "agent_conversion_concurrency_flow")) else "FAIL",
        "task25d": by_name["task25d_regression"]["status"],
        "task25e": by_name["task25e_regression"]["status"],
        "npm_audit": by_name["npm_audit"]["status"],
        "frontend": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("npm_install", "frontend_build", "vue_tsc", "static_frontend_install")) else "FAIL",
        "browser": by_name["browser"]["status"],
        "final_smoke": by_name["final_smoke"]["status"],
    }
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "alembic_expected": "20260712_0015",
        "ordinary_pytest_real_external_api": False,
        "full_reindex": False,
        "package_generated": False,
        "git_commit": False,
        "groups": groups,
        "commands": records,
    }
    write_json("regression.json", payload)
    print(json.dumps({"status": payload["status"], "groups": groups}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
