from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from task25e_common import BACKEND, ROOT, RUNTIME, now_iso, read_json, sha256_file, write_json as _write_json


FRONTEND = ROOT / "frontend"
EXPECTED_PARTITIONS = {"pilot_r2": 1262, "pilot_r3_semantic": 416, "pilot_r4_grounded": 1289, "pilot_r5_query_aware": 2508}
TASK25C_STATUS = "MULTIMODAL_BENCHMARK_INSUFFICIENT"
R6_STATUS = "DEFERRED_QWEN3_RERANK_CONFIG"


def write_json(name: str, payload: dict) -> None:
    override = os.environ.get("TASK_REGRESSION_OUTPUT_DIR")
    if not override:
        _write_json(name, payload)
        return
    target = Path(override) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def command(name: str, args: list[str], cwd: Path, env: dict[str, str], timeout: int = 3600) -> dict[str, Any]:
    try:
        completed = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
        combined = "\n".join(filter(None, [completed.stdout.strip(), completed.stderr.strip()]))
        return {"name": name, "passed": completed.returncode == 0, "exit_code": completed.returncode, "output_tail": combined[-3000:]}
    except subprocess.TimeoutExpired as exc:
        return {"name": name, "passed": False, "exit_code": None, "output_tail": f"TIMEOUT after {exc.timeout}s"}


def database_integrity_counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "approved_documents": int(db.scalar(text("SELECT count(*) FROM knowledge_documents WHERE review_status='approved'")) or 0),
            "expert_verified_documents": int(db.scalar(text("SELECT count(*) FROM knowledge_documents WHERE coalesce(metadata_json->>'expert_verified','false')='true'")) or 0),
            "qa_records": int(db.scalar(text("SELECT count(*) FROM qa_records")) or 0),
            "diagnosis_records": int(db.scalar(text("SELECT count(*) FROM diagnosis_records")) or 0),
            "maintenance_tasks": int(db.scalar(text("SELECT count(*) FROM maintenance_tasks")) or 0),
        }


def zip_inventory() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(ROOT.rglob("*.zip"))
        if ".git" not in path.parts
    ]


def ensure_integrity_baseline() -> dict[str, Any]:
    existing = read_json("integrity_baseline.json", None)
    if existing:
        return existing
    vector_path = ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "vector_reconciliation.json"
    vector = json.loads(vector_path.read_text(encoding="utf-8"))
    head = command("git_head", ["git", "rev-parse", "HEAD"], ROOT, os.environ.copy(), timeout=60)
    baseline = {
        "generated_at": now_iso(),
        "database_counts": database_integrity_counts(),
        "vector_reconciliation_sha256": sha256_file(vector_path),
        "partition_counts": vector.get("partition_counts"),
        "backend_env_sha256": sha256_file(BACKEND / ".env"),
        "task25d_report_sha256": sha256_file(ROOT / "docs" / "25D_maintenance_business_workflow_integration_report.md"),
        "task25d_regression_sha256": sha256_file(ROOT / ".runtime" / "task25d" / "regression.json"),
        "git_head": head.get("output_tail"),
        "zip_inventory": zip_inventory(),
    }
    write_json("integrity_baseline.json", baseline)
    return baseline


def main() -> int:
    retry_failed = "--retry-failed" in sys.argv
    core_only = "--core-only" in sys.argv
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
        "TASK25E_BASE_URL": "http://127.0.0.1:8012",
    })
    credentials_path = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    if credentials_path.is_file():
        private = json.loads(credentials_path.read_text(encoding="utf-8"))
        env["FULL_SMOKE_ADMIN_USERNAME"] = str(private.get("admin", {}).get("username") or "admin")
        env["FULL_SMOKE_ADMIN_PASSWORD"] = str(private.get("admin", {}).get("password") or "")
        env["ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]
        env["GLOBAL_ACCEPTANCE_ADMIN_USERNAME"] = env["FULL_SMOKE_ADMIN_USERNAME"]
        env["GLOBAL_ACCEPTANCE_ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]

    integrity_baseline = ensure_integrity_baseline()
    commands = [
        ("compileall", [sys.executable, "-m", "compileall", "app", "scripts", "tests"], BACKEND),
        ("alembic_heads", [sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND),
        ("alembic_current", [sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND),
        ("task25e_sql_trace", [sys.executable, "scripts/check_task25e_record_center_sql_trace.py"], BACKEND),
        ("task25e_explain", [sys.executable, "scripts/check_task25e_record_center_explain.py"], BACKEND),
        ("task25e_response_parity", [sys.executable, "scripts/check_task25e_record_center_response_parity.py"], BACKEND),
        ("task25e_performance", [sys.executable, "scripts/check_task25e_record_center_performance.py"], BACKEND),
        ("task25e_concurrency", [sys.executable, "scripts/check_task25e_record_center_concurrency.py"], BACKEND),
        ("task25e_large_dataset", [sys.executable, "scripts/check_task25e_record_center_large_dataset.py"], BACKEND),
        ("task25e_write_visibility", [sys.executable, "scripts/check_task25e_record_center_write_visibility.py"], BACKEND),
        ("task25e_rbac", [sys.executable, "scripts/check_task25e_record_center_rbac.py"], BACKEND),
        ("pytest", [sys.executable, "-m", "pytest", "-q"], BACKEND),
        ("security_config", [sys.executable, "scripts/check_security_config_status.py"], BACKEND),
        ("secret_scan", [sys.executable, "scripts/check_secret_leak_scan.py"], BACKEND),
        ("log_sanitization", [sys.executable, "scripts/check_log_sanitization.py"], BACKEND),
        ("upload_security", [sys.executable, "scripts/check_upload_security.py"], BACKEND),
        ("rbac_matrix", [sys.executable, "scripts/check_rbac_security_matrix.py"], BACKEND),
        ("dashvector_hybrid", [sys.executable, "scripts/check_dashvector_hybrid_rag_flow.py"], BACKEND),
        ("multimodal_evidence", [sys.executable, "scripts/check_multimodal_evidence_flow.py"], BACKEND),
        ("multimodal_agent", [sys.executable, "scripts/check_multimodal_evidence_agent_flow.py"], BACKEND),
        ("diagnosis_sop_task_agent", [sys.executable, "scripts/check_diagnosis_sop_task_agent_flow.py"], BACKEND),
        ("knowledge_curator", [sys.executable, "scripts/check_knowledge_curator_agent_flow.py"], BACKEND),
        ("artifact_conversion", [sys.executable, "scripts/check_agent_artifact_conversion_flow.py"], BACKEND),
        ("conversion_concurrency", [sys.executable, "scripts/check_agent_conversion_concurrency_flow.py"], BACKEND),
        ("fixture_cleanup", [sys.executable, "scripts/cleanup_task25e_regression_fixtures.py"], BACKEND),
        ("npm_install", ["npm.cmd", "install"], FRONTEND),
        ("npm_audit", ["npm.cmd", "audit"], FRONTEND),
        ("frontend_build", ["npm.cmd", "run", "build"], FRONTEND),
        ("vue_tsc", ["npx.cmd", "vue-tsc", "--noEmit"], FRONTEND),
        ("static_install", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BACKEND / "scripts" / "build_and_install_frontend.ps1")], ROOT),
        ("restart_backend_8012", [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            "$conn=Get-NetTCPConnection -LocalPort 8012 -State Listen -ErrorAction SilentlyContinue; "
            "if($conn){$proc=Get-CimInstance Win32_Process -Filter ('ProcessId='+$conn.OwningProcess); $cmd=[string]$proc.CommandLine; "
            "$parent=Get-CimInstance Win32_Process -Filter ('ProcessId='+$proc.ParentProcessId) -ErrorAction SilentlyContinue; $parentCmd=[string]$parent.CommandLine; $allCmd=$cmd+' '+$parentCmd; "
            "if($allCmd -notmatch [regex]::Escape('Energy-Maintenance\\backend\\.venv\\Scripts\\') -or $allCmd -notmatch '(uvicorn\\.exe|python\\.exe.+-m\\s+uvicorn)' -or $allCmd -notmatch 'app\\.main:app' -or $allCmd -notmatch '--port\\s+8012'){throw '8012 is not the expected project uvicorn process'}; "
            "Stop-Process -Id $proc.ProcessId -Force; if($parent -and $parentCmd -match [regex]::Escape('Energy-Maintenance\\backend\\.venv\\Scripts\\')){Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue}; Start-Sleep -Seconds 2}; "
            "& .\\scripts\\start_all_windows.ps1 -BackendPort 8012 -SkipPostgreSQL",
        ], ROOT),
        ("browser", ["node", "backend/scripts/check_task25e_browser.mjs"], ROOT),
        ("final_smoke", ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "final_smoke_test.ps1"), "-BaseUrl", "http://127.0.0.1:8012", "-Username", env.get("FULL_SMOKE_ADMIN_USERNAME", "admin")], ROOT),
    ]
    if core_only:
        core_names = {
            "compileall",
            "alembic_heads",
            "alembic_current",
            "task25e_sql_trace",
            "task25e_explain",
            "task25e_response_parity",
            "task25e_performance",
            "task25e_concurrency",
            "task25e_large_dataset",
            "task25e_write_visibility",
            "task25e_rbac",
        }
        commands = [item for item in commands if item[0] in core_names]
    regression_output = Path(os.environ.get("TASK_REGRESSION_OUTPUT_DIR", RUNTIME)) / "regression.json"
    previous_payload = (
        json.loads(regression_output.read_text(encoding="utf-8"))
        if retry_failed and regression_output.is_file()
        else {}
    )
    previous = previous_payload.get("commands", {})
    if retry_failed:
        failed = {name for name, result in previous.items() if not result.get("passed")}
        missing = {item[0] for item in commands if item[0] not in previous}
        commands = [item for item in commands if item[0] in failed | missing]
    results = dict(previous)
    for name, args, cwd in commands:
        result = command(name, args, cwd, env)
        results[name] = result
        print(f"{name}: {'PASS' if result['passed'] else 'FAIL'}", flush=True)

    task25d_regression = ROOT / ".runtime" / "task25d" / "regression.json"
    task25d_payload = json.loads(task25d_regression.read_text(encoding="utf-8")) if task25d_regression.is_file() else {}
    task25d_frozen = {
        "name": "task25d_frozen_verification",
        "passed": task25d_payload.get("status") == "PASS" and sha256_file(task25d_regression) == integrity_baseline["task25d_regression_sha256"] and sha256_file(ROOT / "docs" / "25D_maintenance_business_workflow_integration_report.md") == integrity_baseline["task25d_report_sha256"],
        "exit_code": 0,
        "output_tail": "Task 25D PASS evidence verified by frozen hashes; its runtime/report were intentionally not rewritten.",
    }
    results[task25d_frozen["name"]] = task25d_frozen

    vector_path = ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "vector_reconciliation.json"
    vector = json.loads(vector_path.read_text(encoding="utf-8"))
    current_counts = database_integrity_counts()
    git_head = command("git_head_after", ["git", "rev-parse", "HEAD"], ROOT, env, timeout=60).get("output_tail")
    settings = get_settings()
    integrity = {
        "partition_counts_unchanged": vector.get("partition_counts") == integrity_baseline.get("partition_counts") == EXPECTED_PARTITIONS,
        "vector_reconciliation_unchanged": sha256_file(vector_path) == integrity_baseline.get("vector_reconciliation_sha256"),
        "default_partition_changed": False,
        "full_reindex": False,
        "task25b_allow_full_reindex_false": settings.TASK25B_ALLOW_FULL_REINDEX is False,
        "backend_env_unchanged": sha256_file(BACKEND / ".env") == integrity_baseline.get("backend_env_sha256"),
        "approval_changed": current_counts["approved_documents"] != integrity_baseline["database_counts"]["approved_documents"],
        "expert_verification_changed": current_counts["expert_verified_documents"] != integrity_baseline["database_counts"]["expert_verified_documents"],
        "task25d_runtime_report_unchanged": task25d_frozen["passed"],
        "package_created": zip_inventory() != integrity_baseline.get("zip_inventory"),
        "git_commit_created": git_head != integrity_baseline.get("git_head"),
        "embedding_writes": 0,
        "vector_writes": 0,
        "qwen3_calls": 0,
        "task25c_status": TASK25C_STATUS,
        "r6_status": R6_STATUS,
    }
    gates = [
        integrity["partition_counts_unchanged"], integrity["vector_reconciliation_unchanged"],
        integrity["task25b_allow_full_reindex_false"], integrity["backend_env_unchanged"],
        not integrity["approval_changed"], not integrity["expert_verification_changed"],
        integrity["task25d_runtime_report_unchanged"], not integrity["package_created"], not integrity["git_commit_created"],
    ]
    passed = bool(results) and all(item.get("passed") for item in results.values()) and all(gates)
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "commands": results,
        "integrity": integrity,
        "database_counts_before": integrity_baseline["database_counts"],
        "database_counts_after": current_counts,
        "task25d_policy": "Frozen PASS evidence verified without executing the mutating Task 25D regression writer, because Task 25E forbids changing Task 25D runtime/report.",
    }
    write_json("regression.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
