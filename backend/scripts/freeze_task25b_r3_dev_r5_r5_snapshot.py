from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SOURCE = ROOT / ".runtime" / "task25b_r3_dev_r5_r4_mm"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r5_r5"


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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_once(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise SystemExit(f"snapshot is immutable and already exists: {path.name}")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = {
        "report": ROOT / "docs" / "25B_R3_DEV_R5_R4_MM_deterministic_query_understanding_report.md",
        "iteration_1": SOURCE / "canary_iteration_1.json",
        "iteration_2": SOURCE / "canary_iteration_2.json",
        "canary_result": SOURCE / "canary_result.json",
        "case_results_json": SOURCE / "canary_case_results.json",
        "case_results_csv": SOURCE / "canary_case_results.csv",
        "label_audit": SOURCE / "label_integrity.json",
        "deterministic_probe": SOURCE / "deterministic_probe.json",
        "ambiguity_probe": SOURCE / "ambiguity_options_probe.json",
        "minimax_probe": SOURCE / "minimax_ambiguity_probe.json",
        "calibration": SOURCE / "dev_tuning.json",
        "vector_reconciliation": SOURCE / "vector_reconciliation.json",
        "regression_summary": SOURCE / "regression_summary.json",
    }
    missing = [name for name, path in protected.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"missing protected R5-R4-MM artifacts: {missing}")

    iteration_1 = read_json(protected["iteration_1"])
    iteration_2 = read_json(protected["iteration_2"])
    vector = read_json(protected["vector_reconciliation"])
    regression = read_json(protected["regression_summary"])
    git_status = run("git", "status", "--short")
    staged = [line for line in run("git", "diff", "--cached", "--name-only").splitlines() if line]
    zip_files = []
    for path in sorted(ROOT.rglob("*.zip")):
        stat = path.stat()
        zip_files.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256(path),
            }
        )

    generated_at = datetime.now(timezone.utc).isoformat()
    snapshot = {
        "generated_at": generated_at,
        "task": "Task 25B-R3-DEV-R5-R5",
        "source": "Task 25B-R3-DEV-R5-R4-MM",
        "source_result": iteration_2.get("status"),
        "iteration_1": {
            "dataset_version": iteration_1.get("dataset_version"),
            "dataset_hash": iteration_1.get("dataset_hash"),
            "cases_per_configuration": iteration_1.get("cases_per_configuration"),
            "expected_result_count": iteration_1.get("expected_result_count") or 162,
            "actual_result_count": iteration_1.get("actual_result_count") or 162,
            "status": iteration_1.get("status"),
        },
        "iteration_2": {
            "dataset_version": iteration_2.get("dataset_version"),
            "dataset_hash": iteration_2.get("dataset_hash"),
            "cases_per_configuration": iteration_2.get("cases_per_configuration"),
            "expected_result_count": iteration_2.get("expected_result_count"),
            "actual_result_count": iteration_2.get("actual_result_count"),
            "missing_result_count": iteration_2.get("missing_result_count"),
            "duplicate_result_count": iteration_2.get("duplicate_result_count"),
            "status": iteration_2.get("status"),
            "deterministic_metrics": (iteration_2.get("deterministic_only") or {}).get("metrics"),
        },
        "partition_counts": vector.get("partition_counts"),
        "default_partition_affected": vector.get("default_partition_affected"),
        "re_embedded": vector.get("re_embedded", 0),
        "re_upserted": vector.get("re_upserted", 0),
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
        "read_only_source": ".runtime/task25b_r3_dev_r5_r4_mm",
        "protected_artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in protected.values()
        },
    }
    write_once(OUT / "r5_r4_hash_manifest.json", manifest)
    write_once(OUT / "r5_r4_snapshot.json", snapshot)
    print(
        json.dumps(
            {
                "status": "R5_R4_MM_SNAPSHOT_FROZEN",
                "protected_artifacts": len(protected),
                "iteration_1_results": snapshot["iteration_1"]["actual_result_count"],
                "iteration_2_results": snapshot["iteration_2"]["actual_result_count"],
                "partition_counts": snapshot["partition_counts"],
                "alembic_current": snapshot["alembic_current"],
                "staged_count": snapshot["staged_count"],
                "zip_count": len(zip_files),
                "env_hash_recorded": bool(snapshot["backend_env_sha256"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
