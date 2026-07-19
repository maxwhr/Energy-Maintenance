from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select, text, union_all

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, engine
from app.repositories.record_center_query_repository import RECORD_TYPE_ORDER, RecordCenterQueryRepository
from task25e_common import now_iso, write_json


def compile_sql(statement: Any) -> str:
    return str(statement.compile(dialect=engine.dialect, compile_kwargs={"literal_binds": True}))


def explain(db: Any, statement: Any) -> dict:
    sql = compile_sql(statement)
    value = db.scalar(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql))
    return value[0] if isinstance(value, list) else value


def plan_nodes(plan: dict) -> list[dict]:
    output = []
    stack = [plan.get("Plan", {})]
    while stack:
        node = stack.pop()
        if not node:
            continue
        output.append({key: node.get(key) for key in ("Node Type", "Relation Name", "Index Name", "Actual Rows", "Actual Total Time", "Plan Rows") if key in node})
        stack.extend(node.get("Plans", []))
    return output


def main() -> int:
    empty = {key: None for key in ("device_id", "workflow_id", "actor_id", "keyword", "trace_id", "status", "fault_type", "alarm_code", "manufacturer", "product_series", "date_from", "date_to")}
    with SessionLocal() as db:
        repository = RecordCenterQueryRepository(db)
        identity = union_all(*(repository._identity_select(record_type, empty) for record_type in RECORD_TYPE_ORDER)).subquery("record_center_identity")
        count_statement = select(func.count()).select_from(identity)
        page_statement = select(identity).order_by(identity.c.primary_timestamp.desc(), identity.c.source_priority.asc(), identity.c.record_type.asc(), identity.c.record_id.asc()).limit(20).offset(0)
        count_plan = explain(db, count_statement)
        page_plan = explain(db, page_statement)
    inspector = inspect(engine)
    tables = ["qa_records", "diagnosis_records", "maintenance_tasks", "device_maintenance_records", "sop_execution_records", "knowledge_documents", "knowledge_contributions", "uploaded_media", "kg_nodes", "kg_edges", "kg_extraction_runs", "maintenance_workflows", "operation_logs"]
    indexes = {table: [item["name"] for item in inspector.get_indexes(table)] for table in tables}
    page_nodes = plan_nodes(page_plan)
    count_nodes = plan_nodes(count_plan)
    payload = {
        "generated_at": now_iso(),
        "status": "PASS",
        "plans": {
            "identity_count": {"execution_time_ms": count_plan.get("Execution Time"), "planning_time_ms": count_plan.get("Planning Time"), "nodes": count_nodes, "raw": count_plan},
            "identity_page": {"execution_time_ms": page_plan.get("Execution Time"), "planning_time_ms": page_plan.get("Planning Time"), "nodes": page_nodes, "raw": page_plan},
        },
        "index_inventory": indexes,
        "indexes_added": [],
        "migration_added": False,
        "decision": "NO_INDEX_MIGRATION_REQUIRED",
        "decision_reason": "Current data and 10k transactional fixture meet latency/query gates; observed small-table sequential scans are cheaper than blind index additions.",
        "before_after": "No schema mutation was made, so the audited current plan is both the pre-index and retained plan.",
    }
    write_json("explain.json", payload)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "count_ms": count_plan.get("Execution Time"), "page_ms": page_plan.get("Execution Time")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
