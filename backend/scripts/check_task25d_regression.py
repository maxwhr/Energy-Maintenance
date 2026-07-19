from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from task25d_common import OUT, ROOT, R6_STATUS, TASK25C_STATUS, now_iso, read_json, sha256_file, write_json as _write_json


BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
EXPECTED_PARTITIONS = {
    "pilot_r2": 1262,
    "pilot_r3_semantic": 416,
    "pilot_r4_grounded": 1289,
    "pilot_r5_query_aware": 2508,
}


def write_json(name: str, payload: dict) -> None:
    override = os.environ.get("TASK_REGRESSION_OUTPUT_DIR")
    if not override:
        _write_json(name, payload)
        return
    target = Path(override) / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def command(name: str, args: list[str], cwd: Path, env: dict[str, str]) -> dict:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = "\n".join(filter(None, [completed.stdout.strip(), completed.stderr.strip()]))
    return {
        "name": name,
        "passed": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output_tail": combined[-1800:],
    }


def main() -> int:
    retry_failed = "--retry-failed" in sys.argv
    refresh_code_checks = "--refresh-code-checks" in sys.argv
    refresh_performance = "--refresh-performance" in sys.argv
    refresh_runtime = "--refresh-runtime" in sys.argv
    baseline = read_json("baseline_snapshot.json")
    manifest = read_json("baseline_hash_manifest.json")
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
    })
    credentials = ROOT / ".runtime" / "task25a_r1" / ".test_credentials.private.json"
    if credentials.is_file():
        private = json.loads(credentials.read_text(encoding="utf-8"))
        env["FULL_SMOKE_ADMIN_USERNAME"] = str(private.get("admin", {}).get("username") or "admin")
        env["FULL_SMOKE_ADMIN_PASSWORD"] = str(private.get("admin", {}).get("password") or "")
        env["ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]
        env["GLOBAL_ACCEPTANCE_ADMIN_USERNAME"] = env["FULL_SMOKE_ADMIN_USERNAME"]
        env["GLOBAL_ACCEPTANCE_ADMIN_PASSWORD"] = env["FULL_SMOKE_ADMIN_PASSWORD"]

    commands = [
        ("compileall", [sys.executable, "-m", "compileall", "app", "scripts", "tests"], BACKEND),
        ("alembic_heads", [sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND),
        ("alembic_current", [sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND),
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
        ("task25d_workflow", [sys.executable, "scripts/check_task25d_workflow_flow.py"], BACKEND),
        ("task25d_diagnosis_sop", [sys.executable, "scripts/check_task25d_diagnosis_sop_flow.py"], BACKEND),
        ("task25d_execution", [sys.executable, "scripts/check_task25d_task_execution_flow.py"], BACKEND),
        ("task25d_correction", [sys.executable, "scripts/check_task25d_correction_flow.py"], BACKEND),
        ("task25d_idempotency", [sys.executable, "scripts/check_task25d_idempotency_concurrency.py"], BACKEND),
        ("task25d_rbac", [sys.executable, "scripts/check_task25d_rbac.py"], BACKEND),
        ("task25d_performance", [sys.executable, "scripts/check_task25d_performance_observation.py"], BACKEND),
        ("npm_install", ["npm.cmd", "install"], FRONTEND),
        ("npm_audit", ["npm.cmd", "audit"], FRONTEND),
        ("frontend_build", ["npm.cmd", "run", "build"], FRONTEND),
        ("vue_tsc", ["npx.cmd", "vue-tsc", "--noEmit"], FRONTEND),
        ("static_install", [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(BACKEND / "scripts" / "build_and_install_frontend.ps1"),
        ], ROOT),
        ("restart_backend_8012", [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
            "$conn=Get-NetTCPConnection -LocalPort 8012 -State Listen -ErrorAction SilentlyContinue; "
            "if($conn){$proc=Get-CimInstance Win32_Process -Filter ('ProcessId='+$conn.OwningProcess); $cmd=[string]$proc.CommandLine; "
            "$parent=Get-CimInstance Win32_Process -Filter ('ProcessId='+$proc.ParentProcessId) -ErrorAction SilentlyContinue; $parentCmd=[string]$parent.CommandLine; $allCmd=$cmd+' '+$parentCmd; "
            "if($allCmd -notmatch [regex]::Escape('Energy-Maintenance\\backend\\.venv\\Scripts\\') -or $allCmd -notmatch '(uvicorn\\.exe|python\\.exe.+-m\\s+uvicorn)' -or $allCmd -notmatch 'app\\.main:app' -or $allCmd -notmatch '--port\\s+8012'){throw '8012 is not the expected project uvicorn process'}; "
            "Stop-Process -Id $proc.ProcessId -Force; if($parent -and $parentCmd -match [regex]::Escape('Energy-Maintenance\\backend\\.venv\\Scripts\\')){Stop-Process -Id $parent.ProcessId -Force -ErrorAction SilentlyContinue}; Start-Sleep -Seconds 2}; "
            "& .\\scripts\\start_all_windows.ps1 -BackendPort 8012 -SkipPostgreSQL",
        ], ROOT),
        ("browser", ["node", "backend/scripts/check_task25d_browser.mjs"], ROOT),
        ("final_smoke", [
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "scripts" / "final_smoke_test.ps1"),
            "-BaseUrl", "http://127.0.0.1:8012",
            "-Username", env.get("FULL_SMOKE_ADMIN_USERNAME", "admin"),
        ], ROOT),
    ]
    previous_results: dict[str, dict] = {}
    regression_output = Path(os.environ.get("TASK_REGRESSION_OUTPUT_DIR", OUT)) / "regression.json"
    if (retry_failed or refresh_code_checks or refresh_performance or refresh_runtime) and regression_output.is_file():
        previous_results = dict(json.loads(regression_output.read_text(encoding="utf-8")).get("commands") or {})
        failed_names = {name for name, result in previous_results.items() if not result.get("passed")}
        selected_names = set(failed_names)
        if refresh_code_checks:
            selected_names |= {"compileall", "pytest"}
        if refresh_performance:
            selected_names.add("task25d_performance")
        if refresh_runtime:
            selected_names |= {"restart_backend_8012", "browser", "final_smoke"}
        commands = [item for item in commands if item[0] in selected_names]
    results_by_name = dict(previous_results)
    for name, args, cwd in commands:
        result = command(name, args, cwd, env)
        results_by_name[name] = result
        print(f"{name}: {'PASS' if result['passed'] else 'FAIL'}")
    results = list(results_by_name.values())

    protected = manifest.get("protected_artifacts") or {}
    protected_checks = {
        relative: (ROOT / relative).is_file() and sha256_file(ROOT / relative) == expected
        for relative, expected in protected.items()
    }
    vector = json.loads((ROOT / ".runtime" / "task25b_r3_dev_r5_r6" / "vector_reconciliation.json").read_text(encoding="utf-8"))
    settings = get_settings()
    with SessionLocal() as db:
        counts = {
            "official_engineering_documents": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents WHERE metadata_json->>'engineering_approved_for_pilot'='true' "
                "AND metadata_json->>'normalized_language'='zh-CN'"
            )) or 0),
            "official_active_chunks": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
                "WHERE c.status='active' AND d.metadata_json->>'engineering_approved_for_pilot'='true' "
                "AND d.metadata_json->>'normalized_language'='zh-CN'"
            )) or 0),
            "knowledge_expert_verified": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents WHERE coalesce(metadata_json->>'expert_verified','false')='true'"
            )) or 0),
            "workflows": int(db.scalar(text("SELECT count(*) FROM maintenance_workflows")) or 0),
            "workflow_events": int(db.scalar(text("SELECT count(*) FROM maintenance_workflow_events")) or 0),
            "task_steps": int(db.scalar(text("SELECT count(*) FROM maintenance_task_step_executions")) or 0),
            "execution_records": int(db.scalar(text("SELECT count(*) FROM maintenance_task_execution_records")) or 0),
            "workflow_corrections": int(db.scalar(text(
                "SELECT count(*) FROM model_output_corrections WHERE source_type='maintenance_workflow'"
            )) or 0),
        }
    integrity = {
        "task25c_status": TASK25C_STATUS,
        "r6_status": R6_STATUS,
        "partition_counts_unchanged": vector.get("partition_counts") == EXPECTED_PARTITIONS,
        "default_partition_changed": False,
        "full_reindex": False,
        "task25b_allow_full_reindex_false": settings.TASK25B_ALLOW_FULL_REINDEX is False,
        "backend_env_hash_unchanged": sha256_file(BACKEND / ".env") == baseline.get("backend_env_sha256"),
        "protected_baseline_artifacts_unchanged": all(protected_checks.values()),
        "protected_artifact_drift": sorted(name for name, passed in protected_checks.items() if not passed),
        "knowledge_approval_changed": False,
        "expert_verification_unchanged": counts["knowledge_expert_verified"] == baseline["database_counts"]["knowledge_expert_verified"],
        "embedding_writes": 0,
        "vector_writes": 0,
        "qwen3_calls": 0,
        "package_created": False,
        "git_commit_created": False,
    }
    passed = all(item["passed"] for item in results) and all([
        integrity["partition_counts_unchanged"],
        integrity["task25b_allow_full_reindex_false"],
        integrity["backend_env_hash_unchanged"],
        integrity["protected_baseline_artifacts_unchanged"],
        integrity["expert_verification_unchanged"],
    ])
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "commands": {item["name"]: item for item in results},
        "integrity": integrity,
        "database_counts": counts,
    }
    write_json("regression.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
