from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE = ROOT / ".runtime" / "task25b_r3_dev_r5_r3_mm"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r4_mm"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        args, cwd=cwd, check=True, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return completed.stdout.strip()


def write_once(path: Path, payload: dict) -> None:
    if path.exists():
        raise SystemExit(f"snapshot is immutable and already exists: {path.name}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = {
        "report": ROOT / "docs" / "25B_R3_DEV_R5_R3_MM_query_understanding_contract_report.md",
        "schema_probe": SOURCE / "schema_probe.json",
        "model_ab": SOURCE / "model_ab.json",
        "context_merge": SOURCE / "context_merge_probe.json",
        "planner_probe": SOURCE / "planner_probe.json",
        "contract_gate": SOURCE / "contract_gate.json",
        "vector_reconciliation": SOURCE / "vector_reconciliation.json",
        "regression_summary": SOURCE / "regression_summary.json",
    }
    missing = [name for name, path in protected.items() if not path.exists()]
    if missing:
        raise SystemExit(f"missing protected R5-R3-MM artifacts: {missing}")

    model_ab = json.loads(protected["model_ab"].read_text(encoding="utf-8"))
    contract = json.loads(protected["contract_gate"].read_text(encoding="utf-8"))
    reconciliation = json.loads(protected["vector_reconciliation"].read_text(encoding="utf-8"))
    regression = json.loads(protected["regression_summary"].read_text(encoding="utf-8"))
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
    snapshot = {
        "generated_at": generated_at,
        "task": "Task 25B-R3-DEV-R5-R4-MM",
        "source": "Task 25B-R3-DEV-R5-R3-MM",
        "source_result": contract.get("status"),
        "selected_runtime_model": model_ab.get("selected_runtime_model"),
        "model_ab": {
            name: {
                "structured_success_ratio": metrics.get("structured_success_ratio"),
                "intent_accuracy": metrics.get("intent_accuracy"),
                "canonicalization_accuracy": metrics.get("canonicalization_accuracy"),
                "p95_ms": (metrics.get("latency_ms") or {}).get("p95"),
            }
            for name, metrics in (model_ab.get("models") or {}).items()
        },
        "partition_counts": reconciliation.get("partition_counts"),
        "default_partition_affected": reconciliation.get("default_partition_affected"),
        "re_embedded": reconciliation.get("re_embedded", 0),
        "re_upserted": reconciliation.get("re_upserted", 0),
        "pytest": regression.get("pytest"),
        "alembic_heads": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads", cwd=BACKEND),
        "alembic_current": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "current", cwd=BACKEND),
        "backend_env_sha256": sha256(BACKEND / ".env"),
        "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
        "staged_count": len(staged),
        "zip_files": zip_files,
        "task25b_allow_full_reindex": False,
        "engineering_approval_changed": False,
        "expert_verified_changed": False,
        "formal_full_reindex": False,
    }
    manifest = {
        "algorithm": "sha256",
        "generated_at": generated_at,
        "read_only_source": ".runtime/task25b_r3_dev_r5_r3_mm",
        "protected_artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in protected.values()
        },
    }
    write_once(OUT / "r5_r3_hash_manifest.json", manifest)
    write_once(OUT / "r5_r3_snapshot.json", snapshot)
    print(json.dumps({
        "status": "R5_R3_MM_SNAPSHOT_FROZEN",
        "protected_artifacts": len(protected),
        "partition_counts": snapshot["partition_counts"],
        "alembic_current": snapshot["alembic_current"],
        "staged_count": snapshot["staged_count"],
        "zip_count": len(zip_files),
        "env_hash_recorded": bool(snapshot["backend_env_sha256"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
