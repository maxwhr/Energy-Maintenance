from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import func, select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.models import KGExtractionRun
from app.services.record_center_service import RecordCenterService
from task25e_common import now_iso, write_json


MARKER = "task25e_write_visibility_transactional"


def main() -> int:
    visible = False
    with SessionLocal() as db:
        transaction = db.begin_nested()
        try:
            record = KGExtractionRun(source_type=MARKER, extractor="task25e_fixture", status="pending", metadata_json={"task25e_fixture": True})
            db.add(record)
            db.flush()
            result = RecordCenterService(db).search(record_type="knowledge_graph_extraction_run", keyword=MARKER, page=1, page_size=20)
            visible = any(str(item["record_id"]) == str(record.id) for item in result["items"])
        finally:
            transaction.rollback()
            db.rollback()
    with SessionLocal() as verify:
        remaining = int(verify.scalar(select(func.count()).select_from(KGExtractionRun).where(KGExtractionRun.source_type == MARKER)) or 0)
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if visible and remaining == 0 else "FAIL",
        "cache_enabled": False,
        "immediate_visibility": visible,
        "fixture_cleanup": remaining == 0,
        "covered_write_semantics": ["create record", "flush", "next Record Center query"],
        "production_write_mutations": 0,
    }
    write_json("write_visibility.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
