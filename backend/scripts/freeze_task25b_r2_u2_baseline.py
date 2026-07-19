from __future__ import annotations

import json
import subprocess

from sqlalchemy import func, select

from task25b_r2_u2_common import BACKEND, ROOT, now_iso, sha256_file, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument, RetrievalEvaluationCase
from app.services.vector_store_adapters import DashVectorAdapter


def main() -> int:
    settings = get_settings()
    with SessionLocal() as db:
        database = {
            "documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
            "vector_indexes": int(db.scalar(select(func.count()).select_from(KnowledgeChunkVectorIndex)) or 0),
            "r2_candidates": int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(
                RetrievalEvaluationCase.source_type == "task25b_r2_formal_pilot"
            )) or 0),
        }
    adapter = DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT, api_key=settings.DASHVECTOR_API_KEY,
        collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace=settings.DASHVECTOR_NAMESPACE,
        dimension=settings.DASHVECTOR_DIMENSION, metric=settings.DASHVECTOR_METRIC,
        dtype=settings.DASHVECTOR_DTYPE, timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
        allow_real_api=bool(settings.TASK25B_ALLOW_REAL_API and settings.DASHVECTOR_REAL_CALL_ENABLED),
    )
    partitions = []
    partition_status = "not_checked"
    try:
        result = adapter._request("GET", f"/v1/collections/{settings.DASHVECTOR_PHYSICAL_COLLECTION}/partitions")
        output = result.get("output") or []
        partitions = output if isinstance(output, list) else output.get("partitions") or []
        partitions = sorted(str(item) for item in partitions)
        partition_status = "checked"
    except Exception as exc:
        partition_status = type(exc).__name__
    r2_result = ROOT / ".runtime" / "task25b_r2" / "final_result.json"
    r1_hash = ROOT / ".runtime" / "task25b_r1" / "test_v2_result_hash.json"
    payload = {
        "captured_at": now_iso(),
        "git": {
            "head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip(),
            "status": subprocess.run(["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8").stdout.splitlines(),
        },
        "database": database,
        "config": {
            "embedding_enabled": settings.EMBEDDING_ENABLED,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dim": settings.EMBEDDING_DIM,
            "dashvector_enabled": settings.DASHVECTOR_ENABLED,
            "collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
            "dimension": settings.DASHVECTOR_DIMENSION,
            "metric": settings.DASHVECTOR_METRIC,
            "full_reindex": settings.TASK25B_ALLOW_FULL_REINDEX,
            "env_sha256": sha256_file(BACKEND / ".env"),
            "secret_output": False,
        },
        "partitions": {"status": partition_status, "items": partitions},
        "r2_final_sha256": sha256_file(r2_result) if r2_result.exists() else None,
        "r1_result_sha256": sha256_file(r1_hash) if r1_hash.exists() else None,
        "alembic_current": subprocess.run(
            ["uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "current"],
            cwd=BACKEND, check=True, capture_output=True, text=True, encoding="utf-8",
        ).stdout.strip(),
    }
    write_json("pre_task_snapshot.json", payload)
    print(json.dumps({"status": "FROZEN", "database": database, "partition_count": len(partitions)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
