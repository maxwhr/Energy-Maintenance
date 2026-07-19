from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sqlalchemy import func, select

from task25b_r2_common import BACKEND, ROOT, now_iso, sha256_file, write_json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import KnowledgeChunk, KnowledgeChunkVectorIndex, KnowledgeDocument, RetrievalEvaluationCase
from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


def _safe_config() -> dict:
    settings = get_settings()
    return {
        "captured_at": now_iso(),
        "EMBEDDING_ENABLED": settings.EMBEDDING_ENABLED,
        "EMBEDDING_BASE_URL_configured": bool(settings.EMBEDDING_BASE_URL),
        "EMBEDDING_API_KEY_configured": bool(settings.EMBEDDING_API_KEY),
        "EMBEDDING_MODEL": settings.EMBEDDING_MODEL,
        "EMBEDDING_DIM": settings.EMBEDDING_DIM,
        "EMBEDDING_REAL_CALL_ENABLED": settings.EMBEDDING_REAL_CALL_ENABLED,
        "DASHVECTOR_ENABLED": settings.DASHVECTOR_ENABLED,
        "DASHVECTOR_ENDPOINT_configured": bool(settings.DASHVECTOR_ENDPOINT),
        "DASHVECTOR_ENDPOINT_is_cluster": settings.DASHVECTOR_ENDPOINT.startswith("https://")
        and "dashvector" in settings.DASHVECTOR_ENDPOINT
        and not any(term in settings.DASHVECTOR_ENDPOINT for term in ("help.aliyun", "www.aliyun")),
        "DASHVECTOR_API_KEY_configured": bool(settings.DASHVECTOR_API_KEY),
        "DASHVECTOR_COLLECTION": settings.DASHVECTOR_COLLECTION,
        "DASHVECTOR_PHYSICAL_COLLECTION": settings.DASHVECTOR_PHYSICAL_COLLECTION,
        "DASHVECTOR_MEDIA_COLLECTION": settings.DASHVECTOR_MEDIA_COLLECTION,
        "DASHVECTOR_PHYSICAL_MEDIA_COLLECTION": settings.DASHVECTOR_PHYSICAL_MEDIA_COLLECTION,
        "DASHVECTOR_DIMENSION": settings.DASHVECTOR_DIMENSION,
        "DASHVECTOR_METRIC": settings.DASHVECTOR_METRIC,
        "DASHVECTOR_REAL_CALL_ENABLED": settings.DASHVECTOR_REAL_CALL_ENABLED,
        "TASK25B_ALLOW_REAL_API": settings.TASK25B_ALLOW_REAL_API,
        "TASK25B_ALLOW_FULL_REINDEX": settings.TASK25B_ALLOW_FULL_REINDEX,
        "RETRIEVAL_DEFAULT_MODE": settings.RETRIEVAL_DEFAULT_MODE,
        "env_sha256": sha256_file(BACKEND / ".env"),
        "secrets_output": False,
    }


def _database_snapshot() -> dict:
    with SessionLocal() as db:
        return {
            "documents": int(db.scalar(select(func.count()).select_from(KnowledgeDocument)) or 0),
            "chunks": int(db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0),
            "vector_index_records": int(
                db.scalar(select(func.count()).select_from(KnowledgeChunkVectorIndex)) or 0
            ),
            "evaluation_cases": int(
                db.scalar(select(func.count()).select_from(RetrievalEvaluationCase)) or 0
            ),
        }


def _collection_snapshot(config: dict) -> dict:
    settings = get_settings()
    payload = {
        "captured_at": now_iso(),
        "base_collection": settings.DASHVECTOR_PHYSICAL_COLLECTION,
        "base_media_collection": settings.DASHVECTOR_PHYSICAL_MEDIA_COLLECTION,
        "r1_logical_collection": settings.DASHVECTOR_R1_CANARY_COLLECTION,
        "external_api_called": False,
        "collection_names": [],
        "collection_count": None,
        "status": "not_checked",
    }
    if not (
        config["DASHVECTOR_ENABLED"]
        and config["DASHVECTOR_REAL_CALL_ENABLED"]
        and config["TASK25B_ALLOW_REAL_API"]
        and config["DASHVECTOR_API_KEY_configured"]
    ):
        payload["status"] = "blocked_by_config"
        return payload
    adapter = DashVectorAdapter(
        endpoint=settings.DASHVECTOR_ENDPOINT,
        api_key=settings.DASHVECTOR_API_KEY,
        collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION,
        namespace=settings.DASHVECTOR_NAMESPACE,
        dimension=settings.DASHVECTOR_DIMENSION,
        metric=settings.DASHVECTOR_METRIC,
        dtype=settings.DASHVECTOR_DTYPE,
        timeout_seconds=settings.DASHVECTOR_TIMEOUT_SECONDS,
        allow_real_api=True,
    )
    try:
        result = adapter._request("GET", "/v1/collections")
        output = result.get("output") or []
        items = output if isinstance(output, list) else output.get("collections") or []
        names = sorted(
            str(item.get("name") if isinstance(item, dict) else item)
            for item in items
            if item
        )
        payload.update(
            external_api_called=True,
            collection_names=names,
            collection_count=len(names),
            status="checked",
        )
    except Exception as exc:  # safe diagnostic, no request content or credentials
        payload.update(external_api_called=True, status="error", error=type(exc).__name__)
    return payload


def main() -> int:
    config = _safe_config()
    collections = _collection_snapshot(config)
    r1_files = [
        ROOT / ".runtime" / "task25b_r1" / "test_v2_result_hash.json",
        ROOT / ".runtime" / "task25b_r1" / "test_v2_frozen_manifest.json",
        ROOT / ".runtime" / "task25b_r1" / "blind_quality_gate.json",
    ]
    migration_files = sorted((BACKEND / "alembic" / "versions").glob("*.py"))
    hash_manifest = {
        "captured_at": now_iso(),
        "r1": {str(path.relative_to(ROOT)): sha256_file(path) for path in r1_files},
        "migrations": {str(path.relative_to(ROOT)): sha256_file(path) for path in migration_files},
        "env_sha256": config["env_sha256"],
    }
    r1_result = json.loads(r1_files[0].read_text(encoding="utf-8"))
    snapshot = {
        "captured_at": now_iso(),
        "git": {
            "head": _git("rev-parse", "HEAD"),
            "branch": _git("branch", "--show-current"),
            "status": _git("status", "--short").splitlines(),
        },
        "database": _database_snapshot(),
        "alembic": {
            "expected_head": "20260601_0009",
            "heads_output": subprocess.run(
                ["uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "heads"],
                cwd=BACKEND,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip(),
            "current_output": subprocess.run(
                ["uv", "run", "python", "-m", "alembic", "-c", "alembic.ini", "current"],
                cwd=BACKEND,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip(),
        },
        "r1": {
            "dataset_frozen_hash": r1_result.get("dataset_frozen_hash"),
            "blind_result_sha256": r1_result.get("blind_result_sha256"),
            "formal_blind_runs_completed": r1_result.get("formal_blind_runs_completed"),
            "rerun_allowed": r1_result.get("rerun_allowed"),
        },
        "default_collection": config["DASHVECTOR_PHYSICAL_COLLECTION"],
        "default_retrieval_mode": config["RETRIEVAL_DEFAULT_MODE"],
        "full_reindex_enabled": config["TASK25B_ALLOW_FULL_REINDEX"],
    }
    write_json("pre_task_config_snapshot.json", config)
    write_json("pre_task_collection_snapshot.json", collections)
    write_json("pre_task_hash_manifest.json", hash_manifest)
    write_json("pre_task_snapshot.json", snapshot)
    print(
        json.dumps(
            {
                "status": "FROZEN",
                "r1_hash": snapshot["r1"]["dataset_frozen_hash"],
                "collection_count": collections["collection_count"],
                "secrets_output": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
