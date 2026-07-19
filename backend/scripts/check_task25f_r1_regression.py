from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from task25f_r1_common import BACKEND, ROOT, now_iso, read_json, sha256_file, write_json as _write_json


EXPECTED_ALEMBIC_REVISION = "20260712_0015"


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
    env["TASK25B_ALLOW_FULL_REINDEX"] = "false"
    env.update(
        {
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
        }
    )
    credentials = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    if credentials.is_file():
        private = json.loads(credentials.read_text(encoding="utf-8"))
        admin = private.get("admin") or {}
        env["FULL_SMOKE_ADMIN_USERNAME"] = str(admin.get("username") or "admin")
        env["FULL_SMOKE_ADMIN_PASSWORD"] = str(admin.get("password") or "")
        env["ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]
        env["GLOBAL_ACCEPTANCE_ADMIN_USERNAME"] = env["FULL_SMOKE_ADMIN_USERNAME"]
        env["GLOBAL_ACCEPTANCE_ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]
    return env


def _execute(
    name: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        output = "\n".join(
            value for value in (completed.stdout.strip(), completed.stderr.strip()) if value
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        revision_line = next(
            (line for line in lines if EXPECTED_ALEMBIC_REVISION in line), None
        )
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "last_line": (revision_line or (lines[-1] if lines else ""))[:600],
            "full_output_recorded": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "exit_code": None,
            "status": "TIMEOUT",
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "output_sha256": None,
            "last_line": f"timeout after {exc.timeout}s",
            "full_output_recorded": False,
        }


def _frozen_evidence_record(name: str, key: str) -> dict[str, Any]:
    baseline = json.loads(
        (ROOT / ".runtime" / "task25f" / "baseline.json").read_text(encoding="utf-8")
    )
    evidence = (baseline.get("frozen_evidence") or {}).get(key) or {}
    relative = str(evidence.get("path") or "")
    target = ROOT / relative
    expected = evidence.get("sha256")
    actual = sha256_file(target)
    passed = actual == expected and (target.is_file() if expected else not target.exists())
    return {
        "name": name,
        "command": ["read-only-frozen-evidence-verification", relative],
        "cwd": str(ROOT),
        "exit_code": 0 if passed else 1,
        "status": "PASS" if passed else "FAIL",
        "duration_ms": 0.0,
        "output_sha256": actual,
        "last_line": "frozen evidence unchanged" if passed else "frozen evidence drift detected",
        "expected_sha256": expected,
        "full_output_recorded": False,
    }


def _task25f_immutable_record() -> dict[str, Any]:
    manifest = read_json("task25f_hash_manifest.json", {})
    checks = []
    for item in manifest.get("files") or []:
        target = ROOT / item["path"]
        actual = sha256_file(target)
        checks.append(target.is_file() and actual == item.get("sha256"))
    passed = bool(checks) and all(checks)
    return {
        "name": "task25f_regression",
        "command": [
            "read-only-frozen-evidence-verification",
            ".runtime/task25f",
            "mutating check_task25f_regression.py intentionally not executed",
        ],
        "cwd": str(ROOT),
        "exit_code": 0 if passed else 1,
        "status": "PASS" if passed else "FAIL",
        "duration_ms": 0.0,
        "output_sha256": manifest.get("manifest_hash"),
        "last_line": (
            "all frozen Task 25F hashes unchanged; historical status remains "
            "TASK25F_RAG_COMPATIBILITY_FAILED"
            if passed
            else "frozen Task 25F evidence drift detected"
        ),
        "full_output_recorded": False,
    }


def main() -> int:
    python = str(BACKEND / ".venv" / "Scripts" / "python.exe")
    env = _environment()
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
        ("dashvector_hybrid_rag_flow", [python, "scripts/check_dashvector_hybrid_rag_flow.py"], BACKEND, 300),
        ("multimodal_evidence_flow", [python, "scripts/check_multimodal_evidence_flow.py"], BACKEND, 300),
        ("multimodal_evidence_agent_flow", [python, "scripts/check_multimodal_evidence_agent_flow.py"], BACKEND, 300),
        ("diagnosis_sop_task_agent_flow", [python, "scripts/check_diagnosis_sop_task_agent_flow.py"], BACKEND, 300),
        ("knowledge_curator_agent_flow", [python, "scripts/check_knowledge_curator_agent_flow.py"], BACKEND, 300),
        ("agent_artifact_conversion_flow", [python, "scripts/check_agent_artifact_conversion_flow.py"], BACKEND, 300),
        ("agent_conversion_concurrency_flow", [python, "scripts/check_agent_conversion_concurrency_flow.py"], BACKEND, 300),
        ("regression_fixture_cleanup", [python, "scripts/cleanup_task25f_r1_regression_fixtures.py"], BACKEND, 180),
        (
            "final_smoke",
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "scripts" / "final_smoke_test.ps1"),
                "-BaseUrl",
                "http://127.0.0.1:8012",
                "-Username",
                env.get("FULL_SMOKE_ADMIN_USERNAME", "admin"),
            ],
            ROOT,
            600,
        ),
    ]
    records: list[dict[str, Any]] = []
    for name, command, cwd, timeout in commands:
        record = _execute(name, command, cwd, env, timeout)
        records.append(record)
        print(
            json.dumps(
                {"name": name, "status": record["status"], "last_line": record["last_line"]},
                ensure_ascii=False,
            ),
            flush=True,
        )
        write_json(
            "regression.json",
            {"generated_at": now_iso(), "status": "RUNNING", "commands": records},
        )

    records.extend(
        [
            _frozen_evidence_record("task25d_regression", "task25d_report"),
            _frozen_evidence_record("task25e_regression", "task25e_result"),
            _task25f_immutable_record(),
        ]
    )
    by_name = {item["name"]: item for item in records}
    heads_ok = (
        by_name["alembic_heads"]["status"] == "PASS"
        and EXPECTED_ALEMBIC_REVISION in by_name["alembic_heads"]["last_line"]
    )
    current_ok = (
        by_name["alembic_current"]["status"] == "PASS"
        and EXPECTED_ALEMBIC_REVISION in by_name["alembic_current"]["last_line"]
    )
    passed = all(item["status"] == "PASS" for item in records) and heads_ok and current_ok
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "alembic_expected": EXPECTED_ALEMBIC_REVISION,
        "ordinary_pytest_real_external_api": False,
        "frontend_regression": {
            "status": "NOT_REQUIRED",
            "reason": "Task 25F-R1 did not change a frontend status display or frontend source file.",
        },
        "task25d_task25e_policy": (
            "Read-only frozen PASS evidence verification; the mutating historical regression writers "
            "were not executed because Task 25F-R1 must preserve frozen evidence."
        ),
        "task25f_writer_executed": False,
        "full_reindex": False,
        "embedding_writes": 0,
        "vector_writes": 0,
        "package_generated": False,
        "git_commit": False,
        "groups": {
            "compileall": by_name["compileall"]["status"],
            "alembic": "PASS" if heads_ok and current_ok else "FAIL",
            "pytest": by_name["pytest"]["status"],
            "security": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in (
                    "security_config",
                    "secret_leak_scan",
                    "log_sanitization",
                    "upload_security",
                )
            )
            else "FAIL",
            "rbac": by_name["rbac_matrix"]["status"],
            "rag_flow": by_name["dashvector_hybrid_rag_flow"]["status"],
            "multimodal": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in ("multimodal_evidence_flow", "multimodal_evidence_agent_flow")
            )
            else "FAIL",
            "agents": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in (
                    "diagnosis_sop_task_agent_flow",
                    "knowledge_curator_agent_flow",
                )
            )
            else "FAIL",
            "conversion": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in (
                    "agent_artifact_conversion_flow",
                    "agent_conversion_concurrency_flow",
                )
            )
            else "FAIL",
            "task25d": by_name["task25d_regression"]["status"],
            "task25e": by_name["task25e_regression"]["status"],
            "task25f_frozen": by_name["task25f_regression"]["status"],
            "frontend": "NOT_REQUIRED",
            "final_smoke": by_name["final_smoke"]["status"],
        },
        "commands": records,
    }
    write_json("regression.json", payload)
    print(json.dumps({"status": payload["status"], "groups": payload["groups"]}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
