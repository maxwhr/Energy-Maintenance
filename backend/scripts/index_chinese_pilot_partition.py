from __future__ import annotations

import argparse, json
from pathlib import Path
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import User
from app.services.vector_index_service import VectorIndexService
from task25b_r3_dev_common import RUNTIME, now_iso, write_json


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--allow-real-api", action="store_true"); parser.add_argument("--partition", required=True)
    args = parser.parse_args()
    if not args.allow_real_api or args.partition != "pilot_r2": raise SystemExit("explicit real API flag and pilot_r2 are required")
    gate = json.loads((RUNTIME / "chinese_corpus_gate.json").read_text(encoding="utf-8"))
    if not gate.get("passed"): raise SystemExit("CHINESE_CORPUS_INSUFFICIENT")
    settings = get_settings()
    if settings.TASK25B_ALLOW_FULL_REINDEX: raise SystemExit("TASK25B_ALLOW_FULL_REINDEX must remain false")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin"))
        service = VectorIndexService(db, allow_real_api=True, collection_name=settings.DASHVECTOR_PHYSICAL_COLLECTION, namespace="pilot_r2")
        status = service.status()
        if status.status != "available": raise SystemExit("real embedding/DashVector configuration is blocked")
        config = service._runtime_config(provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector")
        chunks = service.repository.list_stale_chunks(vector_backend="dashvector", collection_name=config["collection_name"],
            namespace="pilot_r2", embedding_model=config["embedding_model"], embedding_provider=config["embedding_provider"], limit=10000)
        result = service._index_chunks(chunks, run_type="chinese_pilot_r2", target_type="all", target_id=None,
            current_user=user, provider=settings.EMBEDDING_PROVIDER, vector_backend="dashvector", force=False)
        payload = {"generated_at": now_iso(), "collection": config["collection_name"], "partition": "pilot_r2",
            "eligible": gate["active_current_chunks"], "processed": result.processed, "embedded": result.succeeded,
            "upserted": result.succeeded, "skipped": result.skipped, "failed": result.failed,
            "default_partition_affected": False, "full_reindex": False, "external_api_called": True}
    write_json("chinese_pilot_index.json", payload); print(payload)


if __name__ == "__main__": main()
