from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from task25d_common import ROOT, R6_STATUS, TASK25C_STATUS, now_iso, sha256_file, write_json


BACKEND = ROOT / "backend"
TASK25C_RUNTIME = ROOT / ".runtime" / "task25c"
R6_RUNTIME = ROOT / ".runtime" / "task25b_r3_dev_r5_r6"


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


def main() -> int:
    settings = get_settings()
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")

    task25c_gate_path = TASK25C_RUNTIME / "multimodal_quality_gate.json"
    task25c_regression_path = TASK25C_RUNTIME / "regression.json"
    r6_config_path = R6_RUNTIME / "config_check.json"
    r6_vector_path = R6_RUNTIME / "vector_reconciliation.json"
    protected = [
        ROOT / "docs" / "25C_multimodal_cross_modal_diagnosis_report.md",
        task25c_gate_path,
        task25c_regression_path,
        TASK25C_RUNTIME / "multimodal_benchmark_v1.json",
        ROOT / "docs" / "25B_R3_DEV_R5_R6_qwen3_dedicated_rerank_report.md",
        r6_config_path,
        r6_vector_path,
    ]
    missing = [str(path) for path in protected if not path.is_file()]
    if missing:
        raise SystemExit(f"missing protected baseline artifacts: {missing}")

    task25c_gate = read_json(task25c_gate_path)
    r6_config = read_json(r6_config_path)
    vector = read_json(r6_vector_path)
    if task25c_gate.get("result") != TASK25C_STATUS:
        raise SystemExit("unexpected Task 25C status")
    if r6_config.get("status") != "QWEN3_RERANK_CONFIG_MISSING":
        raise SystemExit("unexpected R6 configuration status")
    expected_partitions = {
        "pilot_r2": 1262,
        "pilot_r3_semantic": 416,
        "pilot_r4_grounded": 1289,
        "pilot_r5_query_aware": 2508,
    }
    if vector.get("partition_counts") != expected_partitions:
        raise SystemExit("vector baseline mismatch")

    with SessionLocal() as db:
        counts = {
            "official_engineering_documents": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents "
                "WHERE metadata_json->>'engineering_approved_for_pilot'='true' "
                "AND metadata_json->>'normalized_language'='zh-CN'"
            )) or 0),
            "official_active_chunks": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id "
                "WHERE c.status='active' "
                "AND d.metadata_json->>'engineering_approved_for_pilot'='true' "
                "AND d.metadata_json->>'normalized_language'='zh-CN'"
            )) or 0),
            "knowledge_expert_verified": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents "
                "WHERE coalesce(metadata_json->>'expert_verified','false')='true'"
            )) or 0),
            "multimodal_cases": int(db.scalar(text("SELECT count(*) FROM multimodal_maintenance_cases")) or 0),
            "multimodal_evidence": int(db.scalar(text("SELECT count(*) FROM multimodal_evidence_items")) or 0),
            "multimodal_conflicts": int(db.scalar(text("SELECT count(*) FROM multimodal_evidence_conflicts")) or 0),
            "multimodal_hypotheses": int(db.scalar(text("SELECT count(*) FROM multimodal_diagnostic_hypotheses")) or 0),
            "diagnosis_records": int(db.scalar(text("SELECT count(*) FROM diagnosis_records")) or 0),
            "sop_templates": int(db.scalar(text("SELECT count(*) FROM sop_templates")) or 0),
            "maintenance_tasks": int(db.scalar(text("SELECT count(*) FROM maintenance_tasks")) or 0),
            "device_maintenance_records": int(db.scalar(text("SELECT count(*) FROM device_maintenance_records")) or 0),
            "model_output_corrections": int(db.scalar(text("SELECT count(*) FROM model_output_corrections")) or 0),
            "operation_logs": int(db.scalar(text("SELECT count(*) FROM operation_logs")) or 0),
        }

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
    snapshot = {
        "generated_at": generated_at,
        "task": "Task 25D",
        "task25c_status": TASK25C_STATUS,
        "r6_status": R6_STATUS,
        "r6_source_status": r6_config.get("status"),
        "partition_counts": expected_partitions,
        "database_counts": counts,
        "alembic_heads": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads", cwd=BACKEND),
        "alembic_current": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "current", cwd=BACKEND),
        "backend_env_sha256": sha256_file(BACKEND / ".env"),
        "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
        "staged_count": len(staged),
        "zip_files": zip_files,
        "task25b_allow_full_reindex": False,
        "full_reindex": False,
        "qwen3_calls": 0,
        "embedding_writes": 0,
        "vector_writes": 0,
        "knowledge_approval_changed": False,
        "expert_verified_changed": False,
    }
    manifest = {
        "algorithm": "sha256",
        "generated_at": generated_at,
        "protected_artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
            for path in protected
        },
    }
    write_json("baseline_snapshot.json", snapshot, immutable=True)
    write_json("baseline_hash_manifest.json", manifest, immutable=True)
    print(json.dumps({
        "status": "TASK25D_BASELINE_FROZEN",
        "task25c_status": TASK25C_STATUS,
        "r6_status": R6_STATUS,
        "partition_counts": expected_partitions,
        "database_counts": counts,
        "alembic_current": snapshot["alembic_current"],
        "staged_count": len(staged),
        "zip_count": len(zip_files),
        "backend_env_hash_recorded": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
