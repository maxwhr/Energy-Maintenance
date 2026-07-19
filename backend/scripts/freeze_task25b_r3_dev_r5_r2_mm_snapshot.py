from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE = ROOT / ".runtime" / "task25b_r3_dev_r5_r1"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r2_mm"


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


def write_once(path: Path, payload: dict) -> None:
    if path.exists():
        raise SystemExit(f"snapshot is immutable and already exists: {path.name}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = {
        "25B_R3_DEV_R5_R1_query_aware_rag_repair_report.md": ROOT / "docs" / "25B_R3_DEV_R5_R1_query_aware_rag_repair_report.md",
        "structured_model_probe.json": SOURCE / "structured_model_probe.json",
        "rerank_probe.json": SOURCE / "rerank_probe.json",
        "raw_vector_probe.json": SOURCE / "raw_vector_probe.json",
        "fusion_trace.json": SOURCE / "fusion_trace.json",
        "citation_confidence.json": SOURCE / "citation_confidence.json",
        "reconciliation.json": SOURCE / "reconciliation.json",
        "regression_summary.json": SOURCE / "regression_summary.json",
        "canary_result.json": SOURCE / "canary_result.json",
    }
    missing = [name for name, path in protected.items() if not path.exists()]
    if missing:
        raise SystemExit(f"missing protected R5-R1 artifacts: {missing}")

    reconciliation = json.loads(protected["reconciliation.json"].read_text(encoding="utf-8"))
    regression = json.loads(protected["regression_summary.json"].read_text(encoding="utf-8"))
    canary = json.loads(protected["canary_result.json"].read_text(encoding="utf-8"))
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
        "task": "Task 25B-R3-DEV-R5-R2-MM",
        "source": "Task 25B-R3-DEV-R5-R1",
        "source_result": canary.get("result"),
        "source_canary_status": canary.get("status"),
        "structured_probe_status": json.loads(protected["structured_model_probe.json"].read_text(encoding="utf-8")).get("status"),
        "rerank_probe_status": json.loads(protected["rerank_probe.json"].read_text(encoding="utf-8")).get("status"),
        "raw_vector_probe_status": json.loads(protected["raw_vector_probe.json"].read_text(encoding="utf-8")).get("status"),
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
        "expert_verified_changed": False,
        "formal_full_reindex": False,
    }
    manifest = {
        "algorithm": "sha256",
        "generated_at": generated_at,
        "read_only_source": ".runtime/task25b_r3_dev_r5_r1",
        "protected_artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in protected.values()
        },
    }
    write_once(OUT / "r5_r1_hash_manifest.json", manifest)
    write_once(OUT / "r5_r1_snapshot.json", snapshot)
    print(json.dumps({
        "status": "R5_R1_SNAPSHOT_FROZEN",
        "protected_artifacts": len(protected),
        "partition_counts": snapshot["partition_counts"],
        "alembic_current": snapshot["alembic_current"],
        "staged_count": snapshot["staged_count"],
        "zip_count": len(zip_files),
        "env_hash_recorded": bool(snapshot["backend_env_sha256"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
