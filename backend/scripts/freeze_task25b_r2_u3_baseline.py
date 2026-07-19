from __future__ import annotations

import hashlib
import json
import subprocess

from sqlalchemy import func, select

from task25b_r2_u3_common import BACKEND, ROOT, now_iso, sha256_file, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument, RetrievalEvaluationCase


def main() -> int:
    settings = get_settings()
    with SessionLocal() as db:
        payload = {
            "captured_at": now_iso(),
            "git": {
                "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "status_sha256": hashlib.sha256(subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT)).hexdigest(),
            },
            "database": {
                "documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
                "chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
                "vendor_official_documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.source_type == "vendor_official")) or 0),
                "vendor_official_pending": int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.source_type == "vendor_official", KnowledgeDocument.review_status == "pending_review")) or 0),
                "vendor_official_approved": int(db.scalar(select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.source_type == "vendor_official", KnowledgeDocument.review_status == "approved")) or 0),
                "pilot_partition_indexes": int(db.scalar(select(func.count()).select_from(KnowledgeChunkVectorIndex).where(KnowledgeChunkVectorIndex.collection_name == settings.DASHVECTOR_PHYSICAL_COLLECTION, KnowledgeChunkVectorIndex.namespace == settings.DASHVECTOR_PILOT_PARTITION)) or 0),
                "benchmark_total": int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase)) or 0),
                "benchmark_expert_verified": int(db.scalar(select(func.count()).select_from(RetrievalEvaluationCase).where(RetrievalEvaluationCase.review_status == "expert_verified")) or 0),
            },
            "config": {
                "collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
                "pilot_partition": settings.DASHVECTOR_PILOT_PARTITION,
                "dimension": settings.DASHVECTOR_DIMENSION,
                "metric": settings.DASHVECTOR_METRIC,
                "full_reindex": settings.TASK25B_ALLOW_FULL_REINDEX,
                "env_sha256": sha256_file(BACKEND / ".env"),
                "secret_output": False,
            },
            "alembic_current": subprocess.check_output([str(BACKEND / ".venv" / "Scripts" / "alembic.exe"), "-c", "alembic.ini", "current"], cwd=BACKEND, text=True, stderr=subprocess.STDOUT).strip(),
        }
    write_json("pre_task_snapshot.json", payload)
    print(json.dumps({"database": payload["database"], "config": {k: v for k, v in payload["config"].items() if k != "env_sha256"}, "alembic_current": payload["alembic_current"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
