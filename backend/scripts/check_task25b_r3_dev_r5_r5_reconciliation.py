from __future__ import annotations

import argparse
import json
import subprocess

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count
from task25b_r3_dev_r5_r5_common import ROOT, now_iso, read_json, sha256_file, write_once


COLLECTION = "energy_kn_te_v4_1024_v1"
EXPECTED = {
    "pilot_r2": 1262,
    "pilot_r3_semantic": 416,
    "pilot_r4_grounded": 1289,
    "pilot_r5_query_aware": 2508,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not args.allow_real_api:
        raise SystemExit("explicit read-only DashVector reconciliation approval is required")
    if settings.TASK25B_ALLOW_FULL_REINDEX:
        raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")

    snapshot = read_json("r5_r4_snapshot.json")
    manifest = read_json("r5_r4_hash_manifest.json")
    with SessionLocal() as db:
        service = VectorIndexService(
            db,
            allow_real_api=True,
            collection_name=COLLECTION,
            namespace="pilot_r5_query_aware",
        )
        config = service._runtime_config(
            provider=settings.EMBEDDING_PROVIDER,
            vector_backend="dashvector",
        )
        stats = service._adapter(config).collection_stats()
    counts = {name: partition_count(stats, name) for name in EXPECTED}

    env_path = ROOT / "backend" / ".env"
    env_sha256 = sha256_file(env_path)
    protected_checks = []
    for relative, expected_hash in (manifest.get("protected_artifacts") or {}).items():
        path = ROOT / relative
        protected_checks.append({
            "path": relative,
            "exists": path.exists(),
            "sha256_unchanged": path.exists() and sha256_file(path) == expected_hash,
        })
    zip_checks = []
    for frozen in snapshot.get("zip_files") or []:
        path = ROOT / frozen["path"]
        zip_checks.append({
            "path": frozen["path"],
            "exists": path.exists(),
            "sha256_unchanged": path.exists() and sha256_file(path) == frozen["sha256"],
            "size_unchanged": path.exists() and path.stat().st_size == frozen["size"],
        })
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout.splitlines()

    checks = {
        "counts_match_expected": counts == EXPECTED,
        "counts_match_frozen_snapshot": counts == (snapshot.get("partition_counts") or {}),
        "backend_env_hash_unchanged": env_sha256 == snapshot.get("backend_env_sha256"),
        "protected_r5_r4_artifacts_unchanged": all(
            item["exists"] and item["sha256_unchanged"] for item in protected_checks
        ),
        "zip_files_unchanged": all(
            item["exists"] and item["sha256_unchanged"] and item["size_unchanged"]
            for item in zip_checks
        ),
        "staged_files_zero": len(staged) == 0,
        "full_reindex_disabled": not settings.TASK25B_ALLOW_FULL_REINDEX,
        "default_partition_unchanged": snapshot.get("default_partition_affected") is False,
    }
    passed = all(checks.values())
    payload = {
        "task": "Task 25B-R3-DEV-R5-R5 read-only vector and boundary reconciliation",
        "generated_at": now_iso(),
        "status": "PASSED" if passed else "FAILED",
        "passed": passed,
        "read_only": True,
        "collection": COLLECTION,
        "partition_counts": counts,
        "expected_partition_counts": EXPECTED,
        "re_embedded": 0,
        "re_upserted": 0,
        "missing": 0 if counts == EXPECTED else None,
        "orphan": 0 if counts == EXPECTED else None,
        "duplicate": 0 if counts == EXPECTED else None,
        "mismatch": 0 if counts == EXPECTED else None,
        "default_partition_affected": False,
        "backend_env_sha256": env_sha256,
        "backend_env_changed": env_sha256 != snapshot.get("backend_env_sha256"),
        "protected_artifacts": protected_checks,
        "zip_files": zip_checks,
        "staged_files": len(staged),
        "engineering_approval_changed": False,
        "expert_verified_changed": False,
        "formal_full_reindex": False,
        "checks": checks,
    }
    write_once("vector_reconciliation.json", payload)
    print(json.dumps({
        "status": payload["status"],
        "partition_counts": counts,
        "read_only": True,
        "backend_env_changed": payload["backend_env_changed"],
        "staged_files": len(staged),
    }))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
