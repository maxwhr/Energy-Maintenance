from __future__ import annotations

import importlib.metadata
import json
import sys
from pathlib import Path

from sqlalchemy import text

from task25g_common import (
    BACKEND,
    FRONTEND,
    ROOT,
    RUNTIME,
    directory_manifest,
    now_iso,
    platform_facts,
    public_path,
    run,
    sha256_file,
    sha256_value,
    write_json,
)


PROTECTED_TASKS = {
    "task25d": {
        "report": ROOT / "docs" / "25D_maintenance_business_workflow_integration_report.md",
        "runtime": ROOT / ".runtime" / "task25d",
    },
    "task25e": {
        "report": ROOT / "docs" / "25E_record_center_performance_and_stability_report.md",
        "runtime": ROOT / ".runtime" / "task25e",
    },
    "task25f_r1": {
        "report": ROOT / "docs" / "25F_R1_rag_compatibility_and_provider_stability_report.md",
        "runtime": ROOT / ".runtime" / "task25f_r1",
    },
}


def _protected_hashes() -> dict:
    values = {}
    for name, paths in PROTECTED_TASKS.items():
        report = paths["report"]
        runtime = paths["runtime"]
        values[name] = {
            "report": {
                "path": public_path(report),
                "exists": report.is_file(),
                "size": report.stat().st_size if report.is_file() else None,
                "sha256": sha256_file(report),
            },
            "runtime": directory_manifest(runtime),
        }
    return values


def _dependency_baseline() -> dict:
    installed = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            installed.append({"name": name, "version": distribution.version})
    installed.sort(key=lambda item: item["name"].lower())
    files = []
    for path in (
        BACKEND / "pyproject.toml",
        BACKEND / "uv.lock",
        FRONTEND / "package.json",
        FRONTEND / "package-lock.json",
    ):
        files.append({
            "path": public_path(path),
            "exists": path.is_file(),
            "size": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path),
        })
    return {
        "version": "task25g_dependency_baseline_v1",
        "created_at": now_iso(),
        "lockfiles": files,
        "installed_python_distributions": installed,
        "installed_fingerprint": sha256_value(installed),
    }


def _database_snapshot() -> dict:
    try:
        from app.core.database import SessionLocal

        statements = {
            "documents": "SELECT count(*) FROM knowledge_documents",
            "approved_documents": "SELECT count(*) FROM knowledge_documents WHERE review_status='approved'",
            "chunks": "SELECT count(*) FROM knowledge_chunks",
            "active_chunks": "SELECT count(*) FROM knowledge_chunks WHERE status='active'",
            "expert_verified": (
                "SELECT count(*) FROM retrieval_evaluation_cases "
                "WHERE review_status='expert_verified'"
            ),
        }
        with SessionLocal() as session:
            counts = {name: int(session.scalar(text(statement)) or 0) for name, statement in statements.items()}
            partitions = [
                {"namespace": row[0], "count": int(row[1])}
                for row in session.execute(text(
                    "SELECT namespace, count(*) FROM knowledge_chunk_vector_indexes "
                    "GROUP BY namespace ORDER BY namespace"
                )).all()
            ]
        return {"status": "AVAILABLE", "counts": counts, "database_vector_index_namespaces": partitions}
    except Exception as exc:  # noqa: BLE001 - freeze records unavailability without exposing connection values.
        return {"status": "UNAVAILABLE", "error_type": exc.__class__.__name__, "counts": {}, "database_vector_index_namespaces": []}


def _alembic_state() -> dict:
    heads = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], cwd=BACKEND)
    current = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], cwd=BACKEND)
    return {
        "heads_exit_code": heads["exit_code"],
        "heads": heads["stdout"],
        "current_exit_code": current["exit_code"],
        "current": current["stdout"],
    }


def _tool_versions() -> dict:
    probes = {
        "python": run([sys.executable, "--version"]),
        "node": run(["node", "--version"]),
        "npm": run(["npm", "--version"], cwd=FRONTEND),
    }
    return {
        name: {
            "available": probe["exit_code"] == 0,
            "version": probe["stdout"] or probe["stderr"],
        }
        for name, probe in probes.items()
    }


def _git_snapshot() -> dict:
    status = run(["git", "status", "--short"])
    staged = run(["git", "diff", "--cached", "--name-only"])
    return {
        "status_exit_code": status["exit_code"],
        "status_lines": status["stdout"].splitlines() if status["stdout"] else [],
        "status_sha256": sha256_value(status["stdout"].splitlines()),
        "staged_files": staged["stdout"].splitlines() if staged["stdout"] else [],
    }


def _zip_inventory() -> list[dict]:
    return [
        {"path": public_path(path), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(ROOT.rglob("*.zip"))
        if ".git" not in path.parts
    ]


def _task25f_regression_baseline() -> dict:
    path = ROOT / ".runtime" / "task25f_r1" / "regression.json"
    if not path.is_file():
        return {"status": "MISSING", "source": public_path(path)}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "INVALID", "source": public_path(path)}
    return {"status": "FROZEN_SOURCE", "source": public_path(path), "sha256": sha256_file(path), "value": value}


def main() -> int:
    outputs = (
        RUNTIME / "snapshot.json",
        RUNTIME / "hash_manifest.json",
        RUNTIME / "dependency_baseline.json",
        RUNTIME / "frontend_dist_manifest.json",
    )
    if any(path.exists() for path in outputs):
        raise SystemExit("Task 25G snapshot already exists; refusing to overwrite")

    protected = _protected_hashes()
    missing = [
        name
        for name, value in protected.items()
        if not value["report"]["exists"] or value["runtime"]["file_count"] == 0
    ]
    if missing:
        raise SystemExit(f"required protected task evidence missing: {missing}")

    dependency = _dependency_baseline()
    frontend_dist = directory_manifest(FRONTEND / "dist")
    env_path = BACKEND / ".env"
    hash_manifest = {
        "version": "task25g_hash_manifest_v1",
        "created_at": now_iso(),
        "protected_tasks": protected,
        "backend_env": {
            "path": public_path(env_path),
            "exists": env_path.is_file(),
            "sha256": sha256_file(env_path),
            "values_recorded": False,
        },
        "dependency_baseline_sha256": sha256_value(dependency),
        "frontend_dist_sha256": frontend_dist["aggregate_sha256"],
    }
    hash_manifest["manifest_sha256"] = sha256_value(hash_manifest)

    snapshot = {
        "version": "task25g_snapshot_v1",
        "created_at": now_iso(),
        "platform": platform_facts(),
        "tool_versions": _tool_versions(),
        "alembic": _alembic_state(),
        "database": _database_snapshot(),
        "task25f_r1_pytest_baseline": _task25f_regression_baseline(),
        "git": _git_snapshot(),
        "zip_inventory": _zip_inventory(),
        "protected_hash_manifest": hash_manifest["manifest_sha256"],
        "boundaries": {
            "old_task_runtime_writes": 0,
            "database_writes": 0,
            "embedding_calls": 0,
            "dashvector_calls": 0,
            "full_reindex": False,
            "package_generated": False,
            "git_mutation": False,
            "real_machine_acceptance_executed": False,
        },
    }

    write_json("dependency_baseline.json", dependency, overwrite=False)
    write_json("frontend_dist_manifest.json", frontend_dist, overwrite=False)
    write_json("hash_manifest.json", hash_manifest, overwrite=False)
    write_json("snapshot.json", snapshot, overwrite=False)
    print(json.dumps({
        "status": "TASK25G_SNAPSHOT_FROZEN",
        "manifest_sha256": hash_manifest["manifest_sha256"],
        "platform": snapshot["platform"],
        "alembic_current": snapshot["alembic"]["current"],
        "database_status": snapshot["database"]["status"],
        "staged_files": len(snapshot["git"]["staged_files"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
