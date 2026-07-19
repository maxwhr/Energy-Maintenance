from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import func, select

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count
from task25f_common import now_iso, read_json, sha256_file, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not (args.allow_real_api and settings.TASK25B_ALLOW_REAL_API):
        raise SystemExit("explicit read-only DashVector reconciliation approval is required")
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    baseline = read_json("baseline.json", {})
    vector_snapshot = ((baseline.get("vector_partitions") or {}).get("snapshot") or {})
    expected_counts = vector_snapshot.get("partition_counts") or {}
    collection = vector_snapshot.get("collection") or settings.DASHVECTOR_PHYSICAL_COLLECTION

    with SessionLocal() as db:
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=collection, namespace="pilot_r5_query_aware",
        )
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        stats = service._adapter(config).collection_stats()
        database_counts = {
            "knowledge_documents": db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0,
            "approved_documents": db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.review_status == "approved")) or 0,
            "knowledge_chunks": db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0,
            "active_chunks": db.scalar(select(func.count()).select_from(KnowledgeChunk).where(KnowledgeChunk.status == "active")) or 0,
            "semantic_anchors": db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor)) or 0,
        }
    current_counts = {name: partition_count(stats, name) for name in expected_counts}

    frozen_evidence = []
    for name, item in (baseline.get("frozen_evidence") or {}).items():
        path = ROOT / str(item.get("path") or "")
        expected_hash = item.get("sha256")
        unchanged = (sha256_file(path) == expected_hash) if expected_hash else not path.exists()
        refreshed_status = None
        if name == "task25d_regression" and path.is_file() and not unchanged:
            try:
                refreshed_status = json.loads(path.read_text(encoding="utf-8")).get("status")
            except (OSError, ValueError):
                refreshed_status = None
        mandated_refresh = name == "task25d_regression" and refreshed_status == "PASS"
        frozen_evidence.append({
            "name": name,
            "path": item.get("path"),
            "exists": path.is_file(),
            "sha256_unchanged": unchanged,
            "expected_absent": expected_hash is None,
            "mandated_regression_refresh": mandated_refresh,
            "refreshed_status": refreshed_status,
            "status_evidence_preserved": unchanged or mandated_refresh,
        })
    zip_files = []
    for item in baseline.get("zip_inventory") or []:
        path = ROOT / item["path"]
        zip_files.append({
            "path": item["path"],
            "exists": path.is_file(),
            "size_unchanged": path.is_file() and path.stat().st_size == item["size"],
            "sha256_unchanged": path.is_file() and sha256_file(path) == item["sha256"],
        })
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    ).stdout.splitlines()
    checks = {
        "partition_counts_unchanged": current_counts == expected_counts,
        "database_counts_unchanged": database_counts == (baseline.get("database_counts") or {}),
        "backend_env_unchanged": sha256_file(BACKEND / ".env") == baseline.get("backend_env_sha256"),
        "frozen_task_status_evidence_preserved": all(
            item["status_evidence_preserved"] and (item["exists"] or item["expected_absent"])
            for item in frozen_evidence
        ),
        "zip_inventory_unchanged": all(item["exists"] and item["size_unchanged"] and item["sha256_unchanged"] for item in zip_files),
        "staged_zero": not staged,
        "full_reindex_disabled": not settings.TASK25B_ALLOW_FULL_REINDEX,
    }
    passed = all(checks.values())
    payload = {
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "read_only": True,
        "collection": collection,
        "partition_counts": current_counts,
        "expected_partition_counts": expected_counts,
        "database_counts": database_counts,
        "expected_database_counts": baseline.get("database_counts") or {},
        "re_embedded": 0,
        "re_upserted": 0,
        "embedding_writes": 0,
        "vector_writes": 0,
        "default_partition_affected": False,
        "approval_changed": False,
        "engineering_approval_changed": False,
        "expert_verified_changed": False,
        "formal_full_reindex": False,
        "backend_env_changed": not checks["backend_env_unchanged"],
        "frozen_evidence": frozen_evidence,
        "zip_files": zip_files,
        "staged_files": staged,
        "checks": checks,
    }
    write_json("vector_reconciliation.json", payload)
    print(json.dumps({
        "status": payload["status"], "partition_counts": current_counts,
        "database_counts_unchanged": checks["database_counts_unchanged"],
        "backend_env_changed": payload["backend_env_changed"], "staged_files": len(staged),
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
