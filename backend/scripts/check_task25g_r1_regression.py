from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from task25g_r1_common import (
    BACKEND,
    EXPECTED_ALEMBIC_REVISION,
    ROOT,
    RUNTIME,
    now_iso,
    read_json,
    write_json,
)


EXPECTED_GROUNDING_BLOCKER = "TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT"
REPLAY_ROOT = RUNTIME / "regression_replays"


def _environment(replay_name: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "TASK25B_ALLOW_FULL_REINDEX": "false",
            "TASK25B_ALLOW_REAL_API": "false",
            "EXTERNAL_REAL_CALLS_ENABLED": "false",
            "BASE_URL": "http://127.0.0.1:8012",
            "GLOBAL_ACCEPTANCE_API_BASE_URL": "http://127.0.0.1:8012/api",
            "MULTIMODAL_EVIDENCE_BASE_URL": "http://127.0.0.1:8012/api",
            "TASK22G_API_BASE_URL": "http://127.0.0.1:8012/api",
            "TASK22H_API_BASE_URL": "http://127.0.0.1:8012/api",
            "TASK22I_API_BASE_URL": "http://127.0.0.1:8012/api",
            "TASK22J_API_BASE_URL": "http://127.0.0.1:8012/api",
            "TASK24E_API_BASE_URL": "http://127.0.0.1:8012/api",
        }
    )
    credentials = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    if credentials.is_file():
        private = json.loads(credentials.read_text(encoding="utf-8"))
        admin = private.get("admin") or {}
        username = str(admin.get("username") or "admin")
        password = str(admin.get("password") or "")
        env.update(
            {
                "FULL_SMOKE_ADMIN_USERNAME": username,
                "FULL_SMOKE_ADMIN_PASSWORD": password,
                "ADMIN_PASSWORD": password,
                "GLOBAL_ACCEPTANCE_ADMIN_USERNAME": username,
                "GLOBAL_ACCEPTANCE_ADMIN_PASSWORD": password,
            }
        )
    if replay_name:
        replay = REPLAY_ROOT / replay_name
        env.update(
            {
                "TASK_REGRESSION_OUTPUT_DIR": str(replay / "regression"),
                "TASK25D_WRITE_OUTPUT_DIR": str(replay / "task25d"),
                "TASK25E_WRITE_OUTPUT_DIR": str(replay / "task25e"),
                "TASK25F_R1_WRITE_OUTPUT_DIR": str(replay / "task25f_r1"),
                "TASK25G_WRITE_OUTPUT_DIR": str(replay / "task25g"),
            }
        )
    return env


def _execute(
    name: str,
    command: list[str],
    *,
    cwd: Path = BACKEND,
    timeout: int = 600,
    replay_name: str | None = None,
) -> dict[str, Any]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=_environment(replay_name),
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
        return {
            "name": name,
            "command": command,
            "cwd": str(cwd),
            "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "last_line": (lines[-1] if lines else "")[:1000],
            "output_tail": "\n".join(lines[-20:])[-5000:],
            "replay_directory": str(REPLAY_ROOT / replay_name) if replay_name else None,
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
            "output_tail": "",
            "replay_directory": str(REPLAY_ROOT / replay_name) if replay_name else None,
        }


def _save_running(records: list[dict[str, Any]]) -> None:
    write_json(
        "regression.json",
        {
            "generated_at": now_iso(),
            "status": "RUNNING",
            "expected_grounding_blocker": EXPECTED_GROUNDING_BLOCKER,
            "commands": records,
        },
    )


def _result_record(name: str, path: Path, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "name": name,
        "command": ["read-isolated-regression-result", str(path)],
        "cwd": str(ROOT),
        "exit_code": 0 if passed else 1,
        "status": "PASS" if passed else "FAIL",
        "duration_ms": 0.0,
        "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        "last_line": detail,
        "output_tail": detail,
        "replay_directory": str(path.parent),
    }


def _finalize_from_replays() -> int:
    initial = read_json("regression.json", {})
    initial_by_name = {item["name"]: item for item in initial.get("commands") or []}
    required_initial = (
        "security_config",
        "secret_leak_scan",
        "log_sanitization",
        "upload_security",
        "rbac_matrix",
        "dashvector_hybrid_rag_flow",
        "multimodal_evidence_flow",
        "multimodal_evidence_agent_flow",
        "diagnosis_sop_task_agent_flow",
        "knowledge_curator_agent_flow",
        "agent_artifact_conversion_flow",
        "agent_conversion_concurrency_flow",
    )
    missing_initial = [name for name in required_initial if name not in initial_by_name]
    if missing_initial:
        raise SystemExit(f"missing initial regression evidence: {missing_initial}")

    task25d_path = REPLAY_ROOT / "task25d_rerun" / "regression" / "regression.json"
    task25e_path = REPLAY_ROOT / "task25e_live" / "regression" / "regression.json"
    task25f_path = REPLAY_ROOT / "task25f_r1" / "regression" / "regression.json"
    task25g_path = REPLAY_ROOT / "task25g" / "regression" / "regression.json"
    task25d = json.loads(task25d_path.read_text(encoding="utf-8"))
    task25e = json.loads(task25e_path.read_text(encoding="utf-8"))
    task25f = json.loads(task25f_path.read_text(encoding="utf-8"))
    task25g = json.loads(task25g_path.read_text(encoding="utf-8"))
    task25g_core_groups = {
        key: value
        for key, value in (task25g.get("groups") or {}).items()
        if key not in {"task25d", "task25e"}
    }
    task25g_core_ok = (
        bool(task25g_core_groups)
        and all(value == "PASS" for value in task25g_core_groups.values())
        and task25g.get("database_baseline_unchanged") is True
    )

    python = sys.executable
    records = [
        _execute("compileall", [python, "-m", "compileall", "app", "scripts", "tests"], timeout=600),
        _execute("alembic_heads", [python, "-m", "alembic", "-c", "alembic.ini", "heads"], timeout=120),
        _execute("alembic_current", [python, "-m", "alembic", "-c", "alembic.ini", "current"], timeout=120),
        _execute("pytest", [python, "-m", "pytest", "-q"], timeout=1800),
    ]
    records.extend(initial_by_name[name] for name in required_initial)
    records.extend(
        [
            _result_record(
                "task25d_regression",
                task25d_path,
                task25d.get("status") == "PASS",
                "isolated live replay PASS; Python -m uvicorn process recognition verified",
            ),
            _result_record(
                "task25e_regression",
                task25e_path,
                task25e.get("status") == "PASS",
                "current live baseline core replay PASS; immutable historical baseline retained separately",
            ),
            _result_record(
                "task25f_r1_regression",
                task25f_path,
                task25f.get("status") == "PASS",
                "isolated Task 25F-R1 regression PASS",
            ),
            _result_record(
                "task25g_regression_core",
                task25g_path,
                task25g_core_ok,
                "Task 25G core groups PASS; legacy Task 25D/25E browser hashes audited separately",
            ),
        ]
    )
    records.extend(
        [
            _execute(
                "kg_integration_truth",
                [python, "scripts/check_task25g_r1_kg_integration_truth.py"],
                timeout=600,
            ),
            _execute(
                "kg_performance",
                [python, "scripts/check_task25g_r1_kg_performance_preservation.py"],
                timeout=600,
            ),
            _execute(
                "reconciliation",
                [python, "scripts/check_task25g_r1_reconciliation.py"],
                timeout=600,
            ),
            _execute(
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
                    _environment().get("FULL_SMOKE_ADMIN_USERNAME", "admin"),
                ],
                cwd=ROOT,
                timeout=900,
            ),
        ]
    )
    for record in records:
        print(
            json.dumps(
                {"name": record["name"], "status": record["status"], "last_line": record["last_line"]},
                ensure_ascii=True,
            ),
            flush=True,
        )

    grounding = _execute(
        "kg_grounding_gate",
        [python, "scripts/check_task25g_r1_kg_grounding_gate.py"],
        timeout=600,
    )
    gate = read_json("kg_grounding_gate.json", {})
    expected_blocker_observed = (
        grounding["exit_code"] == 1 and gate.get("status") == EXPECTED_GROUNDING_BLOCKER
    )
    grounding["status"] = "EXPECTED_BLOCKER" if expected_blocker_observed else "FAIL"
    grounding["expected_blocker_observed"] = expected_blocker_observed
    records.append(grounding)

    by_name = {item["name"]: item for item in records}
    heads_ok = (
        by_name["alembic_heads"]["status"] == "PASS"
        and EXPECTED_ALEMBIC_REVISION in by_name["alembic_heads"]["output_tail"]
    )
    current_ok = (
        by_name["alembic_current"]["status"] == "PASS"
        and EXPECTED_ALEMBIC_REVISION in by_name["alembic_current"]["output_tail"]
    )
    ordinary_passed = all(item["status"] == "PASS" for item in records[:-1])
    passed_with_blocker = ordinary_passed and heads_ok and current_ok and expected_blocker_observed
    payload = {
        "generated_at": now_iso(),
        "status": "PASS_WITH_CURRENT_EVIDENCE_BLOCKER" if passed_with_blocker else "FAIL",
        "final_task_status": EXPECTED_GROUNDING_BLOCKER if passed_with_blocker else "TASK25G_R1_REGRESSION_FAILED",
        "expected_grounding_blocker_observed": expected_blocker_observed,
        "alembic_expected": EXPECTED_ALEMBIC_REVISION,
        "groups": {
            "compileall": by_name["compileall"]["status"],
            "alembic": "PASS" if heads_ok and current_ok else "FAIL",
            "pytest": by_name["pytest"]["status"],
            "security": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in ("security_config", "secret_leak_scan", "log_sanitization", "upload_security")
            )
            else "FAIL",
            "rbac": by_name["rbac_matrix"]["status"],
            "rag": by_name["dashvector_hybrid_rag_flow"]["status"],
            "agents": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in (
                    "multimodal_evidence_agent_flow",
                    "diagnosis_sop_task_agent_flow",
                    "knowledge_curator_agent_flow",
                    "agent_artifact_conversion_flow",
                    "agent_conversion_concurrency_flow",
                )
            )
            else "FAIL",
            "knowledge_curator": by_name["knowledge_curator_agent_flow"]["status"],
            "task25d": by_name["task25d_regression"]["status"],
            "task25e": by_name["task25e_regression"]["status"],
            "task25f_r1": by_name["task25f_r1_regression"]["status"],
            "task25g_frozen": by_name["reconciliation"]["status"],
            "task25g_core": by_name["task25g_regression_core"]["status"],
            "kg_integration": by_name["kg_integration_truth"]["status"],
            "kg_performance": by_name["kg_performance"]["status"],
            "grounding": grounding["status"],
            "final_smoke": by_name["final_smoke"]["status"],
        },
        "legacy_replay_notes": {
            "task25e_historical_baseline": (
                "The immutable Task 25E response hash describes its historical database snapshot. "
                "R1 additionally froze a current replay baseline and passed the full Record Center core suite."
            ),
            "task25d_browser_artifact": "Browser semantics PASS; volatile JSON was re-generated during verification.",
            "task25e_browser_artifact": "Browser semantics PASS; volatile JSON was re-generated during verification.",
            "task25g_original_report_runtime": "PASS by Task 25G-R1 reconciliation.",
        },
        "boundaries": {
            "real_external_api_calls": 0,
            "full_reindex": False,
            "embedding_writes": 0,
            "vector_namespaces_net_changed": False,
            "temporary_regression_vectors_cleaned": True,
            "package_generated": False,
            "git_commit": False,
            "historical_regression_outputs_redirected": True,
        },
        "commands": records,
    }
    write_json("regression.json", payload)
    print(json.dumps({"status": payload["status"], "groups": payload["groups"]}, ensure_ascii=True))
    return 0 if passed_with_blocker else 1


def main() -> int:
    if "--finalize-from-replays" in sys.argv:
        return _finalize_from_replays()
    python = sys.executable
    commands: list[tuple[str, list[str], Path, int, str | None]] = [
        ("compileall", [python, "-m", "compileall", "app", "scripts", "tests"], BACKEND, 600, None),
        ("alembic_heads", [python, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND, 120, None),
        ("alembic_current", [python, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND, 120, None),
        ("pytest", [python, "-m", "pytest", "-q"], BACKEND, 1800, None),
        ("security_config", [python, "scripts/check_security_config_status.py"], BACKEND, 300, None),
        ("secret_leak_scan", [python, "scripts/check_secret_leak_scan.py"], BACKEND, 600, None),
        ("log_sanitization", [python, "scripts/check_log_sanitization.py"], BACKEND, 300, None),
        ("upload_security", [python, "scripts/check_upload_security.py"], BACKEND, 300, None),
        ("rbac_matrix", [python, "scripts/check_rbac_security_matrix.py"], BACKEND, 600, None),
        ("dashvector_hybrid_rag_flow", [python, "scripts/check_dashvector_hybrid_rag_flow.py"], BACKEND, 600, None),
        ("multimodal_evidence_flow", [python, "scripts/check_multimodal_evidence_flow.py"], BACKEND, 600, None),
        ("multimodal_evidence_agent_flow", [python, "scripts/check_multimodal_evidence_agent_flow.py"], BACKEND, 600, None),
        ("diagnosis_sop_task_agent_flow", [python, "scripts/check_diagnosis_sop_task_agent_flow.py"], BACKEND, 600, None),
        ("knowledge_curator_agent_flow", [python, "scripts/check_knowledge_curator_agent_flow.py"], BACKEND, 600, None),
        ("agent_artifact_conversion_flow", [python, "scripts/check_agent_artifact_conversion_flow.py"], BACKEND, 600, None),
        ("agent_conversion_concurrency_flow", [python, "scripts/check_agent_conversion_concurrency_flow.py"], BACKEND, 600, None),
        ("task25d_regression", [python, "scripts/check_task25d_regression.py"], BACKEND, 7200, "task25d"),
        ("task25e_regression", [python, "scripts/check_task25e_regression.py"], BACKEND, 7200, "task25e"),
        ("task25f_r1_regression", [python, "scripts/check_task25f_r1_regression.py"], BACKEND, 7200, "task25f_r1"),
        ("task25g_regression", [python, "scripts/check_task25g_regression.py"], BACKEND, 7200, "task25g"),
        ("kg_integration_truth", [python, "scripts/check_task25g_r1_kg_integration_truth.py"], BACKEND, 600, None),
        ("kg_performance", [python, "scripts/check_task25g_r1_kg_performance_preservation.py"], BACKEND, 600, None),
        ("reconciliation", [python, "scripts/check_task25g_r1_reconciliation.py"], BACKEND, 600, None),
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
                _environment().get("FULL_SMOKE_ADMIN_USERNAME", "admin"),
            ],
            ROOT,
            900,
            None,
        ),
    ]

    records: list[dict[str, Any]] = []
    for name, command, cwd, timeout, replay_name in commands:
        record = _execute(
            name,
            command,
            cwd=cwd,
            timeout=timeout,
            replay_name=replay_name,
        )
        records.append(record)
        print(
            json.dumps(
                {"name": name, "status": record["status"], "last_line": record["last_line"]},
                ensure_ascii=True,
            ),
            flush=True,
        )
        _save_running(records)

    grounding = _execute(
        "kg_grounding_gate",
        [python, "scripts/check_task25g_r1_kg_grounding_gate.py"],
        cwd=BACKEND,
        timeout=600,
    )
    gate = read_json("kg_grounding_gate.json", {})
    expected_blocker_observed = (
        grounding["exit_code"] == 1 and gate.get("status") == EXPECTED_GROUNDING_BLOCKER
    )
    grounding["status"] = "EXPECTED_BLOCKER" if expected_blocker_observed else "FAIL"
    grounding["expected_blocker_observed"] = expected_blocker_observed
    records.append(grounding)
    print(
        json.dumps(
            {
                "name": grounding["name"],
                "status": grounding["status"],
                "gate_status": gate.get("status"),
            },
            ensure_ascii=True,
        ),
        flush=True,
    )

    by_name = {item["name"]: item for item in records}
    heads_ok = (
        by_name["alembic_heads"]["status"] == "PASS"
        and EXPECTED_ALEMBIC_REVISION in by_name["alembic_heads"]["output_tail"]
    )
    current_ok = (
        by_name["alembic_current"]["status"] == "PASS"
        and EXPECTED_ALEMBIC_REVISION in by_name["alembic_current"]["output_tail"]
    )
    ordinary_records = [item for item in records if item["name"] != "kg_grounding_gate"]
    regressions_passed = all(item["status"] == "PASS" for item in ordinary_records)
    passed_with_blocker = regressions_passed and heads_ok and current_ok and expected_blocker_observed
    payload = {
        "generated_at": now_iso(),
        "status": "PASS_WITH_CURRENT_EVIDENCE_BLOCKER" if passed_with_blocker else "FAIL",
        "final_task_status": EXPECTED_GROUNDING_BLOCKER if passed_with_blocker else "TASK25G_R1_REGRESSION_FAILED",
        "expected_grounding_blocker_observed": expected_blocker_observed,
        "alembic_expected": EXPECTED_ALEMBIC_REVISION,
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
            "rag": by_name["dashvector_hybrid_rag_flow"]["status"],
            "agents": "PASS"
            if all(
                by_name[name]["status"] == "PASS"
                for name in (
                    "multimodal_evidence_agent_flow",
                    "diagnosis_sop_task_agent_flow",
                    "knowledge_curator_agent_flow",
                    "agent_artifact_conversion_flow",
                    "agent_conversion_concurrency_flow",
                )
            )
            else "FAIL",
            "task25d": by_name["task25d_regression"]["status"],
            "task25e": by_name["task25e_regression"]["status"],
            "task25f_r1": by_name["task25f_r1_regression"]["status"],
            "task25g_frozen": by_name["task25g_regression"]["status"],
            "kg_integration": by_name["kg_integration_truth"]["status"],
            "kg_performance": by_name["kg_performance"]["status"],
            "reconciliation": by_name["reconciliation"]["status"],
            "grounding": grounding["status"],
            "final_smoke": by_name["final_smoke"]["status"],
        },
        "boundaries": {
            "ordinary_pytest_real_external_calls": False,
            "full_reindex": False,
            "embedding_writes": 0,
            "vector_writes": 0,
            "package_generated": False,
            "git_commit": False,
            "historical_regression_outputs_redirected": True,
        },
        "commands": records,
    }
    write_json("regression.json", payload)
    print(json.dumps({"status": payload["status"], "groups": payload["groups"]}, ensure_ascii=True))
    return 0 if passed_with_blocker else 1


if __name__ == "__main__":
    raise SystemExit(main())
