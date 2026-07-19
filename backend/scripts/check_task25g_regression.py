from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from sqlalchemy import func, select

from task25g_common import BACKEND, FRONTEND, ROOT, RUNTIME, EXPECTED_ALEMBIC_REVISION, directory_manifest, now_iso, read_json, sha256_file, sha256_value, write_json as _write_json


def write_json(name: str, payload: dict) -> None:
    override = os.environ.get("TASK_REGRESSION_OUTPUT_DIR")
    if not override:
        _write_json(name, payload)
        return
    target = Path(override) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "TASK25B_ALLOW_REAL_API": "false", "TASK25B_ALLOW_FULL_REINDEX": "false",
        "EXTERNAL_REAL_CALLS_ENABLED": "false",
        "BASE_URL": "http://127.0.0.1:8012", "GLOBAL_ACCEPTANCE_API_BASE_URL": "http://127.0.0.1:8012/api",
        "MULTIMODAL_EVIDENCE_BASE_URL": "http://127.0.0.1:8012/api", "TASK22G_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK22H_API_BASE_URL": "http://127.0.0.1:8012/api", "TASK22I_API_BASE_URL": "http://127.0.0.1:8012/api",
        "TASK22J_API_BASE_URL": "http://127.0.0.1:8012/api", "TASK24E_API_BASE_URL": "http://127.0.0.1:8012/api",
    })
    credentials = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    if credentials.is_file():
        value = json.loads(credentials.read_text(encoding="utf-8"))
        admin = value.get("admin") or {}
        env["FULL_SMOKE_ADMIN_USERNAME"] = str(admin.get("username") or "admin")
        env["FULL_SMOKE_ADMIN_PASSWORD"] = str(admin.get("password") or "")
        env["ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]
        env["GLOBAL_ACCEPTANCE_ADMIN_USERNAME"] = env["FULL_SMOKE_ADMIN_USERNAME"]
        env["GLOBAL_ACCEPTANCE_ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]
    return env


def _execute(name: str, command: list[str], cwd: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
    started = perf_counter()
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
        output = "\n".join(value for value in (completed.stdout.strip(), completed.stderr.strip()) if value)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        revision = next((line for line in lines if EXPECTED_ALEMBIC_REVISION in line), None)
        return {
            "name": name, "command": command, "cwd": str(cwd), "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "last_line": (revision or (lines[-1] if lines else ""))[:800], "full_output_recorded": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {"name": name, "command": command, "cwd": str(cwd), "exit_code": None, "status": "TIMEOUT", "duration_ms": round((perf_counter() - started) * 1000, 3), "output_sha256": None, "last_line": f"timeout after {exc.timeout}s", "full_output_recorded": False}


def _capture_database_baseline() -> dict[str, int]:
    from app.core.database import SessionLocal
    from app.models import KnowledgeDocument, RetrievalEvaluationCase
    with SessionLocal() as session:
        return {
            "knowledge_documents": int(session.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "approved_documents": int(session.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.review_status == "approved")) or 0),
            "expert_verified": int(session.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(RetrievalEvaluationCase.review_status == "expert_verified")) or 0),
        }


def _protected_integrity_records() -> list[dict[str, Any]]:
    manifest = read_json("hash_manifest.json", {})
    records = []
    for name, value in (manifest.get("protected_tasks") or {}).items():
        report = value.get("report") or {}
        report_path = ROOT / str(report.get("path") or "")
        report_ok = report_path.is_file() and sha256_file(report_path) == report.get("sha256")
        runtime_expected = value.get("runtime") or {}
        runtime_path = ROOT / str(runtime_expected.get("root") or "")
        runtime_actual = directory_manifest(runtime_path)
        runtime_ok = runtime_actual["aggregate_sha256"] == runtime_expected.get("aggregate_sha256")
        passed = report_ok and runtime_ok
        records.append({
            "name": f"{name}_frozen", "command": ["read-only-frozen-hash-verification", name],
            "cwd": str(ROOT), "exit_code": 0 if passed else 1, "status": "PASS" if passed else "FAIL",
            "duration_ms": 0.0, "output_sha256": sha256_value({"report": sha256_file(report_path), "runtime": runtime_actual["aggregate_sha256"]}),
            "last_line": "report and runtime unchanged" if passed else "frozen evidence drift detected", "full_output_recorded": False,
        })
    return records


def main() -> int:
    python = str(BACKEND / ".venv" / "Scripts" / "python.exe")
    env = _environment()
    pre_database = _capture_database_baseline()
    write_json("regression_pre_database.json", pre_database)
    commands: list[tuple[str, list[str], Path, int]] = [
        ("compileall", [python, "-m", "compileall", "app", "scripts", "tests"], BACKEND, 600),
        ("alembic_heads", [python, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND, 120),
        ("alembic_current", [python, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND, 120),
        ("pytest", [python, "-m", "pytest", "-q"], BACKEND, 1200),
        ("security_config", [python, "scripts/check_security_config_status.py"], BACKEND, 180),
        ("secret_leak_scan", [python, "scripts/check_secret_leak_scan.py"], BACKEND, 300),
        ("log_sanitization", [python, "scripts/check_log_sanitization.py"], BACKEND, 180),
        ("upload_security", [python, "scripts/check_upload_security.py"], BACKEND, 180),
        ("rbac_matrix", [python, "scripts/check_rbac_security_matrix.py"], BACKEND, 300),
        ("rag_flow", [python, "scripts/check_dashvector_hybrid_rag_flow.py"], BACKEND, 300),
        ("multimodal_flow", [python, "scripts/check_multimodal_evidence_flow.py"], BACKEND, 300),
        ("multimodal_agent", [python, "scripts/check_multimodal_evidence_agent_flow.py"], BACKEND, 300),
        ("diagnosis_agent", [python, "scripts/check_diagnosis_sop_task_agent_flow.py"], BACKEND, 300),
        ("curator_agent", [python, "scripts/check_knowledge_curator_agent_flow.py"], BACKEND, 300),
        ("conversion_flow", [python, "scripts/check_agent_artifact_conversion_flow.py"], BACKEND, 300),
        ("conversion_concurrency", [python, "scripts/check_agent_conversion_concurrency_flow.py"], BACKEND, 300),
        ("fixture_cleanup", [python, "scripts/cleanup_task25g_regression_fixtures.py"], BACKEND, 180),
        ("npm_install", ["npm.cmd", "install"], FRONTEND, 300),
        ("npm_audit", ["npm.cmd", "audit", "--audit-level=high"], FRONTEND, 300),
        ("frontend_build", ["npm.cmd", "run", "build"], FRONTEND, 600),
        ("vue_tsc", ["npx.cmd", "vue-tsc", "--noEmit"], FRONTEND, 600),
        ("frontend_portability", [python, "scripts/check_task25g_frontend_portability.py"], BACKEND, 180),
        ("final_smoke", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "final_smoke_test.ps1"), "-BaseUrl", "http://127.0.0.1:8012", "-Username", env.get("FULL_SMOKE_ADMIN_USERNAME", "admin")], ROOT, 600),
    ]
    records = []
    for name, command, cwd, timeout in commands:
        record = _execute(name, command, cwd, env, timeout)
        records.append(record)
        print(json.dumps({"name": name, "status": record["status"], "last_line": record["last_line"]}, ensure_ascii=True), flush=True)
        write_json("regression.json", {"generated_at": now_iso(), "status": "RUNNING", "commands": records})
    records.extend(_protected_integrity_records())
    by_name = {item["name"]: item for item in records}
    post_database = _capture_database_baseline()
    database_unchanged = post_database == pre_database
    heads_ok = by_name["alembic_heads"]["status"] == "PASS" and EXPECTED_ALEMBIC_REVISION in by_name["alembic_heads"]["last_line"]
    current_ok = by_name["alembic_current"]["status"] == "PASS" and EXPECTED_ALEMBIC_REVISION in by_name["alembic_current"]["last_line"]
    passed = all(item["status"] == "PASS" for item in records) and heads_ok and current_ok and database_unchanged
    payload = {
        "generated_at": now_iso(), "status": "PASS" if passed else "FAIL", "alembic_expected": EXPECTED_ALEMBIC_REVISION,
        "pre_database": pre_database, "post_database": post_database, "database_baseline_unchanged": database_unchanged,
        "historical_regression_writers_executed": False, "real_external_api_calls": 0,
        "full_reindex": False, "embedding_writes": 0, "vector_writes": 0, "package_generated": False, "git_commit": False,
        "groups": {
            "compileall": by_name["compileall"]["status"], "alembic": "PASS" if heads_ok and current_ok else "FAIL", "pytest": by_name["pytest"]["status"],
            "security": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("security_config", "secret_leak_scan", "log_sanitization", "upload_security")) else "FAIL",
            "rbac": by_name["rbac_matrix"]["status"], "rag": by_name["rag_flow"]["status"],
            "agents": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("multimodal_agent", "diagnosis_agent", "curator_agent")) else "FAIL",
            "conversion": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("conversion_flow", "conversion_concurrency")) else "FAIL",
            "frontend": "PASS" if all(by_name[name]["status"] == "PASS" for name in ("npm_install", "npm_audit", "frontend_build", "vue_tsc", "frontend_portability")) else "FAIL",
            "task25d": by_name["task25d_frozen"]["status"], "task25e": by_name["task25e_frozen"]["status"], "task25f_r1": by_name["task25f_r1_frozen"]["status"],
            "final_smoke": by_name["final_smoke"]["status"],
        },
        "commands": records,
    }
    write_json("regression.json", payload)
    print(json.dumps({"status": payload["status"], "groups": payload["groups"], "database_unchanged": database_unchanged}, ensure_ascii=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
