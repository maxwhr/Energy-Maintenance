from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from task25b_r3_dev_r5_r6_common import OUT, ROOT, SOURCE, now_iso, sha256_file, write_json


BACKEND = ROOT / "backend"


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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    protected = {
        "report": ROOT / "docs" / "25B_R3_DEV_R5_R5_candidate_recall_and_ranking_report.md",
        "dataset": SOURCE / "train_dev_dataset_v1.json",
        "dataset_manifest": SOURCE / "dataset_manifest.json",
        "dataset_hash_manifest": SOURCE / "dataset_hash_manifest.json",
        "probe": SOURCE / "probe.json",
        "candidate_forensics": SOURCE / "candidate_miss_forensics.json",
        "ranking_forensics": SOURCE / "ranking_forensics.json",
        "intent_forensics": SOURCE / "intent_forensics.json",
        "iteration_1": SOURCE / "canary_iteration_1.json",
        "iteration_2": SOURCE / "canary_iteration_2.json",
        "canary_result": SOURCE / "canary_result.json",
        "case_results_json": SOURCE / "canary_case_results.json",
        "case_results_csv": SOURCE / "canary_case_results.csv",
        "calibration": SOURCE / "dev_tuning.json",
        "formal_lock": SOURCE / "formal_lock.json",
        "vector_reconciliation": SOURCE / "vector_reconciliation.json",
        "browser_review": SOURCE / "browser_review.json",
    }
    missing = [name for name, path in protected.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"missing protected R5-R5 artifacts: {missing}")

    iteration_2 = read_json(protected["iteration_2"])
    dataset = read_json(protected["dataset"])
    vector = read_json(protected["vector_reconciliation"])
    git_status = run("git", "status", "--short")
    staged = [line for line in run("git", "diff", "--cached", "--name-only").splitlines() if line]
    zip_files = []
    for path in sorted(ROOT.rglob("*.zip")):
        stat = path.stat()
        zip_files.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256_file(path),
        })

    generated_at = now_iso()
    metrics = iteration_2.get("metrics") or {}
    snapshot = {
        "generated_at": generated_at,
        "task": "Task 25B-R3-DEV-R5-R6",
        "source": "Task 25B-R3-DEV-R5-R5",
        "source_status": iteration_2.get("status"),
        "dataset_version": dataset.get("dataset_version"),
        "dataset_hash": dataset.get("dataset_hash") or iteration_2.get("dataset_hash"),
        "case_count": int(dataset.get("case_count") or len(dataset.get("rows") or [])),
        "iteration_2_metrics": metrics,
        "partition_counts": vector.get("partition_counts"),
        "default_partition_affected": vector.get("default_partition_affected"),
        "re_embedded": vector.get("re_embedded", 0),
        "re_upserted": vector.get("re_upserted", 0),
        "alembic_heads": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads", cwd=BACKEND),
        "alembic_current": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "current", cwd=BACKEND),
        "backend_env_sha256": sha256_file(BACKEND / ".env"),
        "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
        "staged_count": len(staged),
        "zip_files": zip_files,
        "task25b_allow_full_reindex": False,
        "documents_changed": False,
        "semantic_units_changed": False,
        "engineering_approval_changed": False,
        "expert_verified_changed": False,
        "formal_full_reindex": False,
    }
    manifest = {
        "algorithm": "sha256",
        "generated_at": generated_at,
        "read_only_source": ".runtime/task25b_r3_dev_r5_r5",
        "protected_artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
            for path in protected.values()
        },
    }
    write_json("r5_r5_hash_manifest.json", manifest, immutable=True)
    write_json("r5_r5_snapshot.json", snapshot, immutable=True)
    print(json.dumps({
        "status": "R5_R5_SNAPSHOT_FROZEN",
        "protected_artifacts": len(protected),
        "dataset_version": snapshot["dataset_version"],
        "case_count": snapshot["case_count"],
        "partition_counts": snapshot["partition_counts"],
        "alembic_current": snapshot["alembic_current"],
        "staged_count": snapshot["staged_count"],
        "zip_count": len(zip_files),
        "env_hash_recorded": bool(snapshot["backend_env_sha256"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
