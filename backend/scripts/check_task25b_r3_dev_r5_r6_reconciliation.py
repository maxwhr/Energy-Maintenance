from __future__ import annotations

import argparse
import json
import subprocess

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.vector_index_service import VectorIndexService
from check_task25b_r3_dev_r4_reconciliation import partition_count
from task25b_r3_dev_r5_r6_common import OUT, ROOT, now_iso, read_json, sha256_file, write_json


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
    snapshot = read_json("r5_r5_snapshot.json")
    manifest = read_json("r5_r5_hash_manifest.json")
    with SessionLocal() as db:
        service = VectorIndexService(db, allow_real_api=True, collection_name=COLLECTION, namespace="pilot_r5_query_aware")
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        stats = service._adapter(config).collection_stats()
    counts = {name: partition_count(stats, name) for name in EXPECTED}
    protected = []
    for relative, expected_hash in (manifest.get("protected_artifacts") or {}).items():
        path = ROOT / relative
        protected.append({"path": relative, "exists": path.exists(), "sha256_unchanged": path.exists() and sha256_file(path) == expected_hash})
    env_hash = sha256_file(ROOT / "backend" / ".env")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=ROOT, check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    ).stdout.splitlines()
    zip_files = []
    for frozen in snapshot.get("zip_files") or []:
        path = ROOT / frozen["path"]
        zip_files.append({
            "path": frozen["path"], "exists": path.exists(),
            "sha256_unchanged": path.exists() and sha256_file(path) == frozen["sha256"],
            "size_unchanged": path.exists() and path.stat().st_size == frozen["size"],
        })
    checks = {
        "partition_counts_unchanged": counts == EXPECTED == (snapshot.get("partition_counts") or {}),
        "backend_env_unchanged": env_hash == snapshot.get("backend_env_sha256"),
        "r5_r5_artifacts_unchanged": all(item["exists"] and item["sha256_unchanged"] for item in protected),
        "zip_files_unchanged": all(item["exists"] and item["sha256_unchanged"] and item["size_unchanged"] for item in zip_files),
        "staged_zero": not staged,
        "full_reindex_disabled": not settings.TASK25B_ALLOW_FULL_REINDEX,
    }
    passed = all(checks.values())
    payload = {
        "generated_at": now_iso(), "status": "PASSED" if passed else "FAILED", "passed": passed,
        "read_only": True, "collection": COLLECTION, "partition_counts": counts,
        "expected_partition_counts": EXPECTED, "re_embedded": 0, "re_upserted": 0,
        "default_partition_affected": False, "backend_env_changed": env_hash != snapshot.get("backend_env_sha256"),
        "protected_artifacts": protected, "zip_files": zip_files, "staged_files": len(staged),
        "engineering_approval_changed": False, "expert_verified_changed": False,
        "formal_full_reindex": False, "checks": checks,
    }
    write_json("vector_reconciliation.json", payload)
    print(json.dumps({key: value for key, value in payload.items() if key not in {"protected_artifacts", "zip_files"}}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
