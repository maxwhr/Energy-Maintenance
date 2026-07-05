from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.services.vector_index_service import VectorIndexService  # noqa: E402


def main() -> int:
    settings = get_settings()
    result: dict = {
        "vector_backend": settings.VECTOR_BACKEND,
        "dashvector_enabled": settings.DASHVECTOR_ENABLED,
        "dashvector_endpoint_configured": bool(settings.DASHVECTOR_ENDPOINT),
        "dashvector_api_key_configured": bool(settings.DASHVECTOR_API_KEY),
        "dashvector_collection": settings.DASHVECTOR_COLLECTION,
        "dashvector_dimension": settings.DASHVECTOR_DIMENSION,
        "embedding_enabled": settings.EMBEDDING_ENABLED,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_configured": bool(settings.EMBEDDING_BASE_URL and settings.EMBEDDING_API_KEY and settings.EMBEDDING_MODEL),
        "embedding_dimension": settings.EMBEDDING_DIM,
        "deterministic_test_enabled": settings.EMBEDDING_TEST_PROVIDER_ENABLED,
        "deterministic_test_dimension": settings.EMBEDDING_TEST_DIM,
        "api_keys_masked": True,
        "real_external_call": False,
    }
    try:
        with SessionLocal() as db:
            inspector = inspect(db.bind)
            tables = set(inspector.get_table_names())
            result["metadata_tables"] = {
                "knowledge_chunk_vector_indexes": "knowledge_chunk_vector_indexes" in tables,
                "vector_index_runs": "vector_index_runs" in tables,
            }
            result["alembic_version"] = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
            result["service_status"] = VectorIndexService(db).status().model_dump(mode="json")
    except SQLAlchemyError as exc:
        result["status"] = "blocked"
        result["blocked_reason"] = f"database unavailable: {exc.__class__.__name__}"
        result["metadata_tables"] = {}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    required_tables = result["metadata_tables"]
    if settings.VECTOR_BACKEND != "dashvector":
        print("VECTOR_BACKEND must be dashvector", file=sys.stderr)
        return 1
    if not all(required_tables.values()):
        print("DashVector metadata tables are missing", file=sys.stderr)
        return 1
    if result["service_status"]["status"] != "blocked":
        print("Default config should be blocked because real DashVector/embedding is disabled", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
