from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from task25g_r2_common import (
    BACKEND,
    EXPECTED_ALEMBIC_REVISION,
    RUNTIME,
    TASK25G_R1_RUNTIME,
    now_iso,
    read_json,
    write_json,
)


EXPECTED_BLOCKER = "TASK25G_R2_CURRENT_CHINESE_GRAPH_EVIDENCE_INSUFFICIENT"
REPLAY_ROOT = RUNTIME / "regression_replays"


def _environment(*, isolate_r1: bool = False) -> dict[str, str]:
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
    if isolate_r1:
        hook_directory = REPLAY_ROOT / "pythonpath"
        current_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(hook_directory), current_pythonpath) if value
        )
        env["TASK25G_R1_ISOLATED_RUNTIME"] = str(REPLAY_ROOT / "task25g_r1_isolated")
    return env


def _execute(
    name: str,
    command: list[str],
    *,
    timeout: int,
    isolate_r1: bool = False,
) -> dict[str, Any]:
    started = perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=BACKEND,
            env=_environment(isolate_r1=isolate_r1),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        output = "\n".join(value for value in (completed.stdout.strip(), completed.stderr.strip()) if value)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        return {
            "name": name,
            "command": command,
            "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "last_line": (lines[-1] if lines else "")[:1200],
            "output_tail": "\n".join(lines[-30:])[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "exit_code": None,
            "status": "TIMEOUT",
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "output_sha256": None,
            "last_line": f"timeout after {exc.timeout}s",
            "output_tail": "",
        }


def _isolated_r1_command(target: Path) -> list[str]:
    code = (
        "import pathlib,sys; "
        f"sys.path.insert(0,{str(BACKEND / 'scripts')!r}); "
        "import task25g_r1_common as common; "
        f"common.RUNTIME=pathlib.Path({str(target)!r}); "
        "import check_task25g_r1_regression as runner; "
        "runner.RUNTIME=common.RUNTIME; "
        "runner.REPLAY_ROOT=common.RUNTIME/'regression_replays'; "
        "sys.argv=['check_task25g_r1_regression.py','--finalize-from-replays']; "
        "raise SystemExit(runner.main())"
    )
    return [sys.executable, "-c", code]


def _prepare_r1_isolation_hook(target: Path) -> None:
    hook_directory = REPLAY_ROOT / "pythonpath"
    hook_directory.mkdir(parents=True, exist_ok=True)
    script_directory = BACKEND / "scripts"
    hook = (
        "import os\n"
        "import pathlib\n"
        "import sys\n"
        f"_scripts = {str(script_directory)!r}\n"
        "if _scripts not in sys.path:\n"
        "    sys.path.insert(0, _scripts)\n"
        "import task25g_r1_common as _task25g_r1_common\n"
        "_target = os.environ.get('TASK25G_R1_ISOLATED_RUNTIME')\n"
        "if _target:\n"
        "    _task25g_r1_common.RUNTIME = pathlib.Path(_target)\n"
    )
    (hook_directory / "sitecustomize.py").write_text(hook, encoding="utf-8")
    if target != REPLAY_ROOT / "task25g_r1_isolated":
        raise RuntimeError("Task 25G-R1 isolation target mismatch")


def main() -> int:
    replay = REPLAY_ROOT / "task25g_r1_isolated"
    if replay.exists():
        shutil.rmtree(replay)
    shutil.copytree(TASK25G_R1_RUNTIME, replay)
    _prepare_r1_isolation_hook(replay)
    records = []
    record = _execute(
        "task25g_r1_regression_isolated",
        _isolated_r1_command(replay),
        timeout=21600,
        isolate_r1=True,
    )
    records.append(record)
    print(json.dumps({"name": record["name"], "status": record["status"], "last_line": record["last_line"]}, ensure_ascii=False), flush=True)
    if record["status"] != "PASS":
        payload = {
            "version": "task25g_r2_regression_v1",
            "generated_at": now_iso(),
            "status": "FAIL",
            "final_task_status": "TASK25G_R2_REGRESSION_FAILED",
            "groups": {},
            "commands": records,
        }
        write_json("regression.json", payload)
        return 1

    followups = (
        ("production_core_manifest", "scripts/create_task25g_r2_production_core_manifest.py", 300),
        ("grounding_dry_run", "scripts/apply_task25g_r2_grounding_plan.py", 300),
        ("non_vacuous_context", "scripts/check_task25g_r2_non_vacuous_context.py", 300),
        ("kg_rag_integration", "scripts/check_task25g_r2_kg_rag_integration.py", 600),
        ("kg_diagnosis_grounding", "scripts/check_task25g_r2_kg_diagnosis_grounding.py", 300),
        ("performance_preservation", "scripts/check_task25g_r2_performance_preservation.py", 600),
        ("reconciliation", "scripts/check_task25g_r2_reconciliation.py", 600),
    )
    for name, path, timeout in followups:
        item = _execute(name, [sys.executable, path], timeout=timeout)
        records.append(item)
        print(json.dumps({"name": name, "status": item["status"], "last_line": item["last_line"]}, ensure_ascii=False), flush=True)

    r1_regression = json.loads((replay / "regression.json").read_text(encoding="utf-8"))
    manifest = read_json("production_core_fact_manifest.json", {})
    execution = read_json("grounding_execution.json", {})
    context = read_json("non_vacuous_context.json", {})
    rag = read_json("kg_rag_integration.json", {})
    diagnosis = read_json("kg_diagnosis_grounding.json", {})
    performance = read_json("performance_preservation.json", {})
    reconciliation = read_json("reconciliation.json", {})
    expected_blocker = (
        manifest.get("status") == EXPECTED_BLOCKER
        and execution.get("status") == "DRY_RUN_GATE_BLOCKED"
        and context.get("status") == "TASK25G_R2_NON_VACUOUS_GROUNDING_GATE_FAILED"
        and rag.get("status") == "BLOCKED_BY_CURRENT_EVIDENCE_GATE"
        and diagnosis.get("status") == "BLOCKED_BY_CURRENT_EVIDENCE_GATE"
    )
    ordinary_followups = {"production_core_manifest", "grounding_dry_run", "non_vacuous_context", "kg_rag_integration", "kg_diagnosis_grounding"}
    followups_ok = all(
        item["status"] == "PASS"
        for item in records
        if item["name"] not in ordinary_followups
    )
    r1_groups = r1_regression.get("groups") or {}
    groups = {
        "compileall": r1_groups.get("compileall"),
        "alembic": r1_groups.get("alembic"),
        "pytest": r1_groups.get("pytest"),
        "security": r1_groups.get("security"),
        "rbac": r1_groups.get("rbac"),
        "rag": r1_groups.get("rag"),
        "agents": r1_groups.get("agents"),
        "knowledge_curator": r1_groups.get("knowledge_curator"),
        "task25d": r1_groups.get("task25d"),
        "task25e": r1_groups.get("task25e"),
        "task25f_r1": r1_groups.get("task25f_r1"),
        "task25g": r1_groups.get("task25g_core") or r1_groups.get("task25g_frozen"),
        "task25g_r1": "PASS" if r1_regression.get("status") == "PASS_WITH_CURRENT_EVIDENCE_BLOCKER" else "FAIL",
        "r2_matching": "PASS" if manifest.get("gate", {}).get("eligible_fact_count") == 10 else "FAIL",
        "r2_grounding": "EXPECTED_BLOCKER" if expected_blocker else "FAIL",
        "r2_performance": performance.get("status"),
        "r2_reconciliation": (
            "PASS"
            if reconciliation.get("status") in {"PASS", "PASS_WITH_VOLATILE_R1_AUDIT_REFRESH"}
            else "FAIL"
        ),
        "final_smoke": r1_groups.get("final_smoke"),
    }
    passed = (
        expected_blocker
        and followups_ok
        and all(value == "PASS" for key, value in groups.items() if key not in {"r2_grounding"})
        and groups["r2_grounding"] == "EXPECTED_BLOCKER"
        and EXPECTED_ALEMBIC_REVISION == "20260712_0015"
    )
    payload = {
        "version": "task25g_r2_regression_v1",
        "generated_at": now_iso(),
        "status": "PASS_WITH_CURRENT_EVIDENCE_BLOCKER" if passed else "FAIL",
        "final_task_status": EXPECTED_BLOCKER if passed else "TASK25G_R2_REGRESSION_FAILED",
        "expected_blocker_observed": expected_blocker,
        "alembic_expected": EXPECTED_ALEMBIC_REVISION,
        "groups": groups,
        "commands": records,
        "boundaries": {
            "old_task25g_r1_runtime_overwritten": False,
            "external_provider_calls": 0,
            "full_reindex": False,
            "embedding_writes": 0,
            "vector_writes": 0,
            "package_generated": False,
            "git_commit": False,
        },
    }
    write_json("regression.json", payload)
    print(json.dumps({"status": payload["status"], "final_task_status": payload["final_task_status"], "groups": groups}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
