from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

from sqlalchemy import delete, func, insert, select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.models import KGExtractionRun
from app.services.record_center_service import RecordCenterService
from task25e_common import SQLTrace, latency_summary, now_iso, write_json


MARKER = "task25e_large_dataset_transactional"


def main() -> int:
    results = {}
    sql_counts = []
    cleanup = False
    with SessionLocal() as db:
        original_count = int(db.scalar(select(func.count()).select_from(KGExtractionRun)) or 0)
        transaction = db.begin_nested()
        inserted = 0
        try:
            for target in (1000, 5000, 10000):
                addition = target - inserted
                db.execute(
                    insert(KGExtractionRun),
                    [
                        {
                            "source_type": MARKER,
                            "extractor": "task25e_fixture",
                            "status": "pending",
                            "candidate_count": index,
                            "approved_count": 0,
                            "rejected_count": 0,
                            "metadata_json": {"task25e_fixture": True},
                        }
                        for index in range(inserted, target)
                    ],
                )
                db.flush()
                inserted = target
                service = RecordCenterService(db)
                service.overview()
                values = []
                for _ in range(7):
                    started = perf_counter()
                    service.overview()
                    values.append((perf_counter() - started) * 1000)
                with SQLTrace(db.get_bind()) as trace:
                    response = service.overview()
                sql_counts.append(len(trace.statements))
                results[str(target)] = {**latency_summary(values), "sql_count": len(trace.statements), "visible_total": response["knowledge_graph_extraction_runs"]}
        finally:
            transaction.rollback()
            db.rollback()
    with SessionLocal() as verify:
        remaining = int(verify.scalar(select(func.count()).select_from(KGExtractionRun).where(KGExtractionRun.source_type == MARKER)) or 0)
        final_count = int(verify.scalar(select(func.count()).select_from(KGExtractionRun)) or 0)
        cleanup = remaining == 0 and final_count == original_count
    passed = cleanup and len(set(sql_counts)) == 1 and results["10000"]["p95_ms"] <= 1500
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if passed else "FAIL",
        "fixture_scope": "nested transaction rolled back; no existing business IDs selected or deleted",
        "results": results,
        "sql_count_growth": max(sql_counts) - min(sql_counts) if sql_counts else None,
        "cleanup": cleanup,
        "remaining_fixture_rows": remaining,
        "original_count": original_count,
        "final_count": final_count,
    }
    write_json("large_dataset.json", payload)
    print(json.dumps({"status": payload["status"], "p95_10k": results.get("10000", {}).get("p95_ms"), "sql_growth": payload["sql_count_growth"], "cleanup": cleanup}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
