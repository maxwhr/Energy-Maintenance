from __future__ import annotations

import json
import sys
from pathlib import Path

from task25f_r1_common import (
    BACKEND,
    ROOT,
    RUNTIME,
    TASK25F_RUNTIME,
    git_lines,
    now_iso,
    run,
    safe_settings_snapshot,
    sha256_file,
    sha256_value,
    write_json,
)


FROZEN_TASK25F_FILES = (
    ROOT / "docs" / "25F_rag_end_to_end_performance_and_stability_report.md",
    TASK25F_RUNTIME / "result.json",
    TASK25F_RUNTIME / "baseline.json",
    TASK25F_RUNTIME / "baseline_query_results.json",
    TASK25F_RUNTIME / "response_parity.json",
    TASK25F_RUNTIME / "provider_trace.json",
    TASK25F_RUNTIME / "stage_trace.json",
    TASK25F_RUNTIME / "concurrency.json",
    TASK25F_RUNTIME / "failure_degradation.json",
    TASK25F_RUNTIME / "vector_reconciliation.json",
    TASK25F_RUNTIME / "performance_suite_manifest.json",
)


def _inventory() -> list[dict]:
    rows = []
    for path in FROZEN_TASK25F_FILES:
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "exists": path.is_file(),
            "size": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path),
        })
    return rows


def _zip_inventory() -> list[dict]:
    return [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(ROOT.rglob("*.zip"))
        if ".git" not in path.parts
    ]


def _alembic_state() -> dict:
    heads = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], cwd=BACKEND)
    current = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], cwd=BACKEND)
    return {
        "heads_exit_code": heads["exit_code"],
        "heads": heads["stdout"],
        "current_exit_code": current["exit_code"],
        "current": current["stdout"],
    }


def main() -> int:
    snapshot_path = RUNTIME / "task25f_snapshot.json"
    manifest_path = RUNTIME / "task25f_hash_manifest.json"
    if snapshot_path.exists() or manifest_path.exists():
        raise SystemExit("Task 25F-R1 frozen snapshot already exists; refusing to overwrite")
    inventory = _inventory()
    missing = [item["path"] for item in inventory if not item["exists"]]
    if missing:
        raise SystemExit(f"Task 25F frozen evidence missing: {missing}")
    suite = json.loads((TASK25F_RUNTIME / "performance_suite_manifest.json").read_text(encoding="utf-8"))
    result = json.loads((TASK25F_RUNTIME / "result.json").read_text(encoding="utf-8"))
    settings = safe_settings_snapshot()
    manifest_body = {
        "version": "task25f_r1_hash_manifest_v1",
        "created_at": now_iso(),
        "immutable_source": ".runtime/task25f",
        "files": inventory,
        "query_suite_sha256": suite.get("dataset_sha256"),
        "query_suite_case_count": suite.get("case_count"),
        "config_fingerprint": sha256_value(settings),
        "backend_env_sha256": sha256_file(BACKEND / ".env"),
    }
    manifest_body["manifest_hash"] = sha256_value(manifest_body)
    write_json(manifest_path, manifest_body, overwrite=False)
    staged = git_lines("diff", "--cached", "--name-only")
    git_status = git_lines("status", "--short")
    snapshot = {
        "version": "task25f_r1_snapshot_v1",
        "created_at": now_iso(),
        "source_task": "Task 25F",
        "source_status": result.get("status") or result.get("result"),
        "source_result": result,
        "task25f_runtime_mutated": False,
        "query_suite": {
            "dataset_version": suite.get("dataset_version"),
            "case_count": suite.get("case_count"),
            "sha256": suite.get("dataset_sha256"),
        },
        "settings": settings,
        "config_fingerprint": manifest_body["config_fingerprint"],
        "backend_env_sha256": manifest_body["backend_env_sha256"],
        "alembic": _alembic_state(),
        "git": {
            "status_lines": git_status,
            "status_hash": sha256_value(git_status),
            "staged_files": staged,
        },
        "zip_inventory": _zip_inventory(),
        "task25f_hash_manifest": manifest_body["manifest_hash"],
        "boundaries": {
            "full_reindex": False,
            "embedding_writes": 0,
            "vector_writes": 0,
            "package_generated": False,
            "git_commit": False,
        },
    }
    write_json(snapshot_path, snapshot, overwrite=False)
    print(json.dumps({
        "status": "TASK25F_R1_SNAPSHOT_FROZEN",
        "source_status": snapshot["source_status"],
        "cases": suite.get("case_count"),
        "manifest_hash": manifest_body["manifest_hash"],
        "staged_files": len(staged),
        "alembic_current": snapshot["alembic"]["current"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
