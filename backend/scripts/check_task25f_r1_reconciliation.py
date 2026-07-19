from __future__ import annotations

import argparse
import json

from sqlalchemy import func, select

from task25f_r1_common import (
    BACKEND,
    ROOT,
    TASK25F_RUNTIME,
    git_lines,
    read_json,
    safe_settings_snapshot,
    sha256_file,
    write_json,
)

from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument, MaintenanceSemanticAnchor
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = safe_settings_snapshot()
    if not (args.allow_real_api and settings["TASK25B_ALLOW_REAL_API"]):
        raise SystemExit("explicit read-only --allow-real-api approval is required")
    if settings["TASK25B_ALLOW_FULL_REINDEX"]:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    frozen = read_json("task25f_snapshot.json", {})
    hashes = read_json("task25f_hash_manifest.json", {})
    baseline = json.loads((TASK25F_RUNTIME / "baseline.json").read_text(encoding="utf-8"))
    vector_snapshot = ((baseline.get("vector_partitions") or {}).get("snapshot") or {})
    expected_partitions = vector_snapshot.get("partition_counts") or {}
    collection = vector_snapshot.get("collection") or settings["DASHVECTOR_PHYSICAL_COLLECTION"]
    with SessionLocal() as db:
        service = VectorIndexService(
            db, allow_real_api=True, collection_name=collection, namespace="pilot_r5_query_aware"
        )
        config = service._runtime_config(provider=settings["EMBEDDING_PROVIDER"], vector_backend="dashvector")
        stats = service._adapter(config).collection_stats()
        database_counts = {
            "knowledge_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "approved_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(
                KnowledgeDocument.review_status == "approved"
            )) or 0),
            "knowledge_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
            "active_chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk).where(
                KnowledgeChunk.status == "active"
            )) or 0),
            "semantic_anchors": int(db.scalar(select(func.count()).select_from(MaintenanceSemanticAnchor)) or 0),
        }
    current_partitions = {name: partition_count(stats, name) for name in expected_partitions}
    task25f_files = []
    for item in hashes.get("files") or []:
        path = ROOT / item["path"]
        task25f_files.append({
            "path": item["path"],
            "exists": path.is_file(),
            "expected_sha256": item.get("sha256"),
            "actual_sha256": sha256_file(path),
            "unchanged": path.is_file() and sha256_file(path) == item.get("sha256"),
        })
    protected = []
    for name, item in (baseline.get("frozen_evidence") or {}).items():
        if name not in {"task25c_report", "task25c_result", "r6_report", "r6_config", "r6_probe"}:
            continue
        path = ROOT / str(item.get("path") or "")
        expected_hash = item.get("sha256")
        protected.append({
            "name": name,
            "path": item.get("path"),
            "exists": path.is_file(),
            "expected_absent": expected_hash is None,
            "unchanged": sha256_file(path) == expected_hash,
            "preserved": (not path.exists()) if expected_hash is None else (
                path.is_file() and sha256_file(path) == expected_hash
            ),
        })
    current_zips = {
        path.relative_to(ROOT).as_posix(): {"size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in ROOT.rglob("*.zip") if ".git" not in path.parts
    }
    expected_zips = {item["path"]: {"size": item["size"], "sha256": item["sha256"]} for item in frozen.get("zip_inventory") or []}
    staged = git_lines("diff", "--cached", "--name-only")
    checks = {
        "partition_counts_unchanged": current_partitions == expected_partitions,
        "database_counts_unchanged": database_counts == (baseline.get("database_counts") or {}),
        "task25f_files_unchanged": all(item["unchanged"] for item in task25f_files),
        "task25c_and_r6_unchanged": all(item["preserved"] for item in protected),
        "backend_env_unchanged": sha256_file(BACKEND / ".env") == frozen.get("backend_env_sha256"),
        "zip_inventory_unchanged": current_zips == expected_zips,
        "staged_zero": not staged,
        "full_reindex_disabled": settings["TASK25B_ALLOW_FULL_REINDEX"] is False,
    }
    passed = all(checks.values())
    payload = {
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "read_only": True,
        "collection": collection,
        "partition_counts": current_partitions,
        "expected_partition_counts": expected_partitions,
        "database_counts": database_counts,
        "expected_database_counts": baseline.get("database_counts") or {},
        "task25f_files": task25f_files,
        "protected_task25c_r6": protected,
        "staged_files": staged,
        "embedding_writes": 0,
        "vector_writes": 0,
        "full_reindex": False,
        "default_partition_changed": False,
        "pilot_r2_changed": False,
        "pilot_r3_changed": False,
        "pilot_r4_changed": False,
        "pilot_r5_changed": False,
        "approval_changed": False,
        "expert_verification_changed": False,
        "backend_env_changed": not checks["backend_env_unchanged"],
        "package_generated": False,
        "git_commit": False,
        "checks": checks,
    }
    write_json("vector_reconciliation.json", payload)
    print(json.dumps({
        "status": payload["status"], "partitions": current_partitions,
        "database_unchanged": checks["database_counts_unchanged"],
        "task25f_unchanged": checks["task25f_files_unchanged"],
        "task25c_r6_unchanged": checks["task25c_and_r6_unchanged"],
        "staged": len(staged),
    }, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
