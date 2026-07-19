from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import KnowledgeChunkVectorIndex, MaintenanceSemanticAnchor, RetrievalEvaluationCase
from task25b_r3_dev_r5_common import OUT, R4_OUT, now_iso, sha256_file, sha256_text, write_json


R4_FILES = (
    "r3_snapshot.json",
    "r3_hash_manifest.json",
    "semantic_unit_manifest.json",
    "semantic_unit_quality.json",
    "semantic_unit_reconciliation.json",
    "embedding_margin.json",
    "canary_iteration_1.json",
    "canary_iteration_2.json",
    "canary_result.json",
)


def main() -> None:
    root = OUT.parents[1]
    git_status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    ).stdout
    env_path = root / "backend" / ".env"
    with SessionLocal() as db:
        counts = {
            "pilot_r2": int(db.scalar(select(func.count()).select_from(KnowledgeChunkVectorIndex).where(
                KnowledgeChunkVectorIndex.namespace == "pilot_r2"
            )) or 0),
            "pilot_r3_semantic": int(db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor).where(
                MaintenanceSemanticAnchor.namespace == "pilot_r3_semantic"
            )) or 0),
            "pilot_r4_grounded": int(db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor).where(
                MaintenanceSemanticAnchor.namespace == "pilot_r4_grounded"
            )) or 0),
            "r5_formal_cases": int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
                RetrievalEvaluationCase.metadata_json["dataset_version"].as_string() == "task25b_r3_dev_r5_llm_zh_v1"
            )) or 0),
            "expert_verified_total": int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
                RetrievalEvaluationCase.review_status == "expert_verified"
            )) or 0),
        }
    artifact_hashes = {name: sha256_file(R4_OUT / name) for name in R4_FILES}
    if any(value is None for value in artifact_hashes.values()):
        missing = [name for name, value in artifact_hashes.items() if value is None]
        raise SystemExit(f"R4 baseline artifacts missing: {missing}")
    snapshot = {
        "generated_at": now_iso(),
        "read_only": True,
        "task": "Task 25B-R3-DEV-R5",
        "r4_result": "DEVELOPMENT_ENGINEERING_VECTOR_RECALL_NOT_PROVEN",
        "collection": "energy_kn_te_v4_1024_v1",
        "partition_counts": counts,
        "alembic_current": "20260712_0012",
        "task25b_allow_full_reindex": False,
        "default_partition_changed": False,
        "formal_full_reindex": False,
        "formal_test_created": False,
        "formal_run_count": 0,
        "expert_verified_changed": False,
        "backend_env_sha256": sha256_file(env_path),
        "git_status_sha256": sha256_text(git_status),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
        "r4_artifact_hashes": artifact_hashes,
    }
    manifest = {
        "algorithm": "sha256",
        "generated_at": snapshot["generated_at"],
        "read_only": True,
        "snapshot": {"r5_baseline_snapshot.json": None},
        "r4_artifacts": artifact_hashes,
    }
    snapshot_path = write_json("r5_baseline_snapshot.json", snapshot)
    manifest["snapshot"][snapshot_path.name] = sha256_file(snapshot_path)
    write_json("r5_baseline_hash_manifest.json", manifest)
    print({"status": "FROZEN", "partitions": counts, "r4_artifacts": len(artifact_hashes)})


if __name__ == "__main__":
    main()
