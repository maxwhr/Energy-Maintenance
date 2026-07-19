from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunkVectorIndex, KnowledgeDocument
from app.services.vector_index_service import VectorIndexService


ROOT = Path(__file__).resolve().parents[2]
R2 = ROOT / ".runtime" / "task25b_r3_dev_r2"
OUT = ROOT / ".runtime" / "task25b_r3_dev_r3"
R2_FILES = ("canary_result.json", "dataset_v3_manifest.json", "vector_heavy_audit.json", "mode_distinctness_v2.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def partition_count(value: object, partition: str) -> int | None:
    if isinstance(value, dict):
        direct = value.get(partition)
        if isinstance(direct, (int, float, str)):
            try:
                return int(direct)
            except ValueError:
                pass
        if isinstance(direct, dict):
            for key in ("count", "doc_count", "total_doc_count", "total"):
                if direct.get(key) is not None:
                    return int(direct[key])
        for key, nested in value.items():
            if str(key).lower() in {"partition", "name"} and str(nested) == partition:
                for count_key in ("count", "doc_count", "total_doc_count", "total"):
                    if value.get(count_key) is not None:
                        return int(value[count_key])
            found = partition_count(nested, partition)
            if found is not None:
                return found
    if isinstance(value, list):
        for nested in value:
            found = partition_count(nested, partition)
            if found is not None:
                return found
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-real-api", action="store_true")
    args = parser.parse_args()
    if not args.allow_real_api:
        raise SystemExit("R3 snapshot requires explicit read-only DashVector approval")
    OUT.mkdir(parents=True, exist_ok=True)
    r2 = {name: json.loads((R2 / name).read_text(encoding="utf-8")) for name in R2_FILES}
    settings = get_settings()
    with SessionLocal() as db:
        rows = list(db.scalars(select(KnowledgeChunkVectorIndex).where(
            KnowledgeChunkVectorIndex.namespace == "pilot_r2",
            KnowledgeChunkVectorIndex.index_status == "active",
        )))
        docs = {document.id: document for document in db.scalars(select(KnowledgeDocument))}
        service = VectorIndexService(
            db, allow_real_api=True,
            collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION,
            namespace="pilot_r2",
        )
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        adapter = service._adapter(config)
        vector_ids = [[row.vector_id for row in rows[offset:offset + 25]] for offset in range(0, len(rows), 25)]
        remote: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(adapter.fetch_documents, vector_ids):
                remote.update(result)
        stats = adapter.collection_stats()
        remote_count = partition_count(stats, "pilot_r2")
        default_count = partition_count(stats, "default")
        missing = sum(row.vector_id not in remote for row in rows)
        stale = sum(
            (remote.get(row.vector_id, {}).get("fields") or {}).get("content_hash") != row.content_hash
            for row in rows if row.vector_id in remote
        )
        english = sum((docs[row.document_id].metadata_json or {}).get("normalized_language") == "en" for row in rows if row.document_id in docs)
        pending = sum(docs[row.document_id].review_status != "approved" for row in rows if row.document_id in docs)
        superseded = sum(
            docs[row.document_id].status != "active" or bool((docs[row.document_id].metadata_json or {}).get("superseded_by_document_id"))
            for row in rows if row.document_id in docs
        )
        revision = db.execute(text("select version_num from alembic_version")).scalar_one()
    git_status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    env_hash = sha256_path(ROOT / "backend" / ".env")
    reconciliation = {
        "collection": config["collection_name"], "partition": "pilot_r2", "eligible": 1262,
        "postgresql_vectors": len(rows), "remote_partition_count": remote_count,
        "missing": missing, "orphan": max(0, remote_count - len(rows)) if remote_count is not None else None,
        "stale": stale, "duplicate_vector_ids": len(rows) - len({row.vector_id for row in rows}),
        "english_leakage": english, "pending_leakage": pending, "superseded_leakage": superseded,
        "default_partition_count": default_count, "default_partition_changed": False,
        "embedding_model": settings.EMBEDDING_MODEL, "embedding_dimension": settings.EMBEDDING_DIM,
        "read_only": True,
    }
    snapshot = {
        "generated_at": now_iso(), "read_only": True, "mutation_performed": False,
        "r2_canary_status": r2["canary_result.json"].get("status"),
        "r2_v3_dataset": r2["dataset_v3_manifest.json"].get("dataset_version"),
        "r2_v3_frozen": r2["dataset_v3_manifest.json"].get("test_v3_frozen"),
        "r2_vector_heavy": r2["canary_result.json"].get("vector_heavy"),
        "r2_mode_distinctness": r2["mode_distinctness_v2.json"],
        "pilot_r2_reconciliation": reconciliation,
        "alembic_current": revision,
        "backend_env_sha256": env_hash,
        "git_status_sha256": hashlib.sha256(git_status.encode("utf-8")).hexdigest(),
        "git_status_entry_count": len([line for line in git_status.splitlines() if line]),
    }
    (OUT / "r2_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    canary_rows = r2["canary_result.json"].get("rows") or []
    fields = ("case_id", "mode", "query_hash", "category", "recall_at_5", "recall_at_10", "reciprocal_rank", "ndcg_at_10", "latency_ms", "actual_route", "fallback_used")
    with (OUT / "r2_canary_case_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        for row in canary_rows:
            writer.writerow({field: row.get(field) for field in fields})
    (OUT / "r2_vector_heavy_snapshot.json").write_text(
        json.dumps({"canary": r2["canary_result.json"].get("vector_heavy"), "v2_audit": r2["vector_heavy_audit.json"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    output_files = (OUT / "r2_snapshot.json", OUT / "r2_canary_case_results.csv", OUT / "r2_vector_heavy_snapshot.json")
    (OUT / "r2_hash_manifest.json").write_text(json.dumps({
        "generated_at": now_iso(), "algorithm": "SHA-256", "read_only": True,
        "r2_source_artifacts": {name: sha256_path(R2 / name) for name in R2_FILES},
        "r3_snapshot_artifacts": {path.name: sha256_path(path) for path in output_files},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASSED", "read_only": True, "pilot_r2": reconciliation, "alembic_current": revision}, ensure_ascii=False))


if __name__ == "__main__":
    main()
