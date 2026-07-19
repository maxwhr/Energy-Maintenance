from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from task25c_common import DEFERRED_RERANK_STATUS, ROOT, now_iso, sha256_file, write_json


BACKEND = ROOT / "backend"
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
    protected = [
        ROOT / "docs" / "25B_R3_DEV_R5_R6_qwen3_dedicated_rerank_report.md",
        R6_RUNTIME / "r5_r5_snapshot.json",
        R6_RUNTIME / "r5_r5_hash_manifest.json",
        R6_RUNTIME / "config_check.json",
        R6_RUNTIME / "qwen_rerank_probe.json",
        R6_RUNTIME / "qwen_rerank_probe_cases.csv",
        R6_RUNTIME / "vector_reconciliation.json",
        R6_RUNTIME / "browser_review.json",
        R6_RUNTIME / "final_smoke.json",
    ]
    missing = [str(path) for path in protected if not path.is_file()]
    if missing:
        raise SystemExit(f"missing R6 baseline artifacts: {missing}")

    r6_config = read_json(R6_RUNTIME / "config_check.json")
    vector = read_json(R6_RUNTIME / "vector_reconciliation.json")
    if r6_config.get("status") != "QWEN3_RERANK_CONFIG_MISSING":
        raise SystemExit("unexpected R6 configuration status")
    expected_partitions = {
        "pilot_r2": 1262,
        "pilot_r3_semantic": 416,
        "pilot_r4_grounded": 1289,
        "pilot_r5_query_aware": 2508,
    }
    if vector.get("partition_counts") != expected_partitions:
        raise SystemExit("vector baseline does not match Task 25C boundary")

    with SessionLocal() as db:
        db_counts = {
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
            "semantic_unit_v2": int(db.scalar(text(
                "SELECT count(*) FROM maintenance_semantic_anchors "
                "WHERE namespace='pilot_r5_query_aware' AND index_status='active'"
            )) or 0),
            "knowledge_expert_verified": int(db.scalar(text(
                "SELECT count(*) FROM knowledge_documents "
                "WHERE coalesce(metadata_json->>'expert_verified','false')='true'"
            )) or 0),
            "uploaded_media": int(db.scalar(text("SELECT count(*) FROM uploaded_media")) or 0),
            "media_processing_jobs": int(db.scalar(text("SELECT count(*) FROM media_processing_jobs")) or 0),
            "media_ocr_results": int(db.scalar(text("SELECT count(*) FROM media_ocr_results")) or 0),
            "media_ai_analyses": int(db.scalar(text("SELECT count(*) FROM media_ai_analyses")) or 0),
            "media_evidence_links": int(db.scalar(text("SELECT count(*) FROM media_evidence_links")) or 0),
            "diagnosis_records": int(db.scalar(text("SELECT count(*) FROM diagnosis_records")) or 0),
            "sop_templates": int(db.scalar(text("SELECT count(*) FROM sop_templates")) or 0),
            "maintenance_tasks": int(db.scalar(text("SELECT count(*) FROM maintenance_tasks")) or 0),
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
        "task": "Task 25C",
        "r6_status": DEFERRED_RERANK_STATUS,
        "r6_source_status": r6_config.get("status"),
        "r6_real_calls_allowed": False,
        "partition_counts": expected_partitions,
        "default_partition_changed": False,
        "re_embedded": 0,
        "re_upserted": 0,
        "database_counts": db_counts,
        "alembic_heads": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads", cwd=BACKEND),
        "alembic_current": run(sys.executable, "-m", "alembic", "-c", "alembic.ini", "current", cwd=BACKEND),
        "backend_env_sha256": sha256_file(BACKEND / ".env"),
        "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
        "staged_count": len(staged),
        "zip_files": zip_files,
        "task25b_allow_full_reindex": False,
        "knowledge_approval_changed": False,
        "expert_verified_changed": False,
        "formal_full_reindex": False,
    }
    manifest = {
        "algorithm": "sha256",
        "generated_at": generated_at,
        "protected_r6_artifacts": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256_file(path)
            for path in protected
        },
    }
    write_json("baseline_snapshot.json", snapshot, immutable=True)
    write_json("baseline_hash_manifest.json", manifest, immutable=True)
    write_json("r6_deferred_status.json", {
        "generated_at": generated_at,
        "status": DEFERRED_RERANK_STATUS,
        "source_status": r6_config.get("status"),
        "reason": "DASHSCOPE_RERANK_BASE_URL_MISSING",
        "application_blocked": False,
        "multimodal_development_blocked": False,
        "query_aware_fallback": "deterministic",
        "qwen3_api_called": False,
        "r6_probe_called": False,
        "r6_canary_called": False,
        "r6_formal_called": False,
    }, immutable=True)
    print(json.dumps({
        "status": "TASK25C_BASELINE_FROZEN",
        "r6_status": DEFERRED_RERANK_STATUS,
        "partition_counts": expected_partitions,
        "database_counts": db_counts,
        "alembic_current": snapshot["alembic_current"],
        "staged_count": len(staged),
        "zip_count": len(zip_files),
        "backend_env_hash_recorded": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
