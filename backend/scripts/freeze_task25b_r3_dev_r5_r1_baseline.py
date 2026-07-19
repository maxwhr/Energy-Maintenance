from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE = ROOT / ".runtime" / "task25b_r3_dev_r5"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = {
        "canary_iteration_1.json": SOURCE / "canary_iteration_1.json",
        "canary_iteration_2.json": SOURCE / "canary_iteration_2.json",
        "canary_result.json": SOURCE / "canary_result.json",
        "query_understanding_metrics.json": SOURCE / "query_understanding_metrics.json",
        "25B_R3_DEV_R5_query_aware_grounded_rag_report.md": ROOT / "docs" / "25B_R3_DEV_R5_query_aware_grounded_rag_report.md",
    }
    missing = [name for name, path in protected.items() if not path.exists()]
    if missing:
        raise SystemExit(f"missing protected R5 artifacts: {missing}")

    reconciliation = json.loads((SOURCE / "reconciliation.json").read_text(encoding="utf-8"))
    git_status = run("git", "status", "--short")
    staged = [line for line in run("git", "diff", "--cached", "--name-only").splitlines() if line]
    zip_files = []
    for path in sorted(ROOT.rglob("*.zip")):
        stat = path.stat()
        zip_files.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256(path),
        })

    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "algorithm": "sha256",
        "generated_at": generated_at,
        "read_only_source": ".runtime/task25b_r3_dev_r5",
        "protected_artifacts": {name: sha256(path) for name, path in protected.items()},
    }
    baseline = {
        "generated_at": generated_at,
        "task": "Task 25B-R3-DEV-R5-R1",
        "source_result": "QUERY_AWARE_GROUNDED_RAG_QUALITY_GATE_FAILED",
        "source_canary_iteration_1_status": json.loads(protected["canary_iteration_1.json"].read_text(encoding="utf-8"))["status"],
        "source_canary_iteration_2_status": json.loads(protected["canary_iteration_2.json"].read_text(encoding="utf-8"))["status"],
        "source_canary_result_status": json.loads(protected["canary_result.json"].read_text(encoding="utf-8"))["status"],
        "collection": reconciliation["collection"],
        "partition_counts": {
            **reconciliation["old_partition_counts"],
            "pilot_r5_query_aware": reconciliation["remote_partition_count"],
        },
        "default_partition_affected": reconciliation["default_partition_affected"],
        "original_vectors_reindexed": reconciliation["original_vectors_reindexed"],
        "alembic_heads": run("uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "heads", cwd=BACKEND),
        "alembic_current": run("uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "current", cwd=BACKEND),
        "backend_env_sha256": sha256(BACKEND / ".env"),
        "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
        "staged_count": len(staged),
        "zip_files": zip_files,
        "task25b_allow_full_reindex": False,
        "expert_verified_changed": False,
        "formal_full_reindex": False,
    }
    write_json(OUT / "r5_failed_hash_manifest.json", manifest)
    write_json(OUT / "r5_failed_baseline.json", baseline)
    print(json.dumps({
        "status": "R5_FAILED_BASELINE_FROZEN",
        "artifacts": len(protected),
        "partitions": baseline["partition_counts"],
        "alembic_current": baseline["alembic_current"],
        "staged_count": baseline["staged_count"],
        "zip_count": len(zip_files),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
