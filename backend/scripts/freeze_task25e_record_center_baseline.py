from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import perf_counter

from sqlalchemy import func, select

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.models import (
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KGEdge,
    KGExtractionRun,
    KGNode,
    KnowledgeContribution,
    KnowledgeDocument,
    MaintenanceTask,
    QARecord,
    SOPExecutionRecord,
    UploadedMedia,
    User,
)
from app.services.record_center_service import RecordCenterService
from task25e_common import (
    ROOT,
    RUNTIME,
    SQLTrace,
    latency_summary,
    now_iso,
    run,
    sha256_file,
    sha256_value,
    write_json,
)


MODELS = {
    "qa_records": QARecord,
    "diagnosis_records": DiagnosisRecord,
    "maintenance_tasks": MaintenanceTask,
    "maintenance_records": DeviceMaintenanceRecord,
    "sop_executions": SOPExecutionRecord,
    "knowledge_documents": KnowledgeDocument,
    "knowledge_contributions": KnowledgeContribution,
    "uploaded_media": UploadedMedia,
    "devices": Device,
    "knowledge_graph_nodes": KGNode,
    "knowledge_graph_edges": KGEdge,
    "knowledge_graph_extraction_runs": KGExtractionRun,
}


def _ids(items: list[dict]) -> list[str]:
    return [f"{item.get('record_type')}:{item.get('record_id')}" for item in items]


def _zip_inventory() -> list[dict]:
    output = []
    for path in sorted(ROOT.rglob("*.zip")):
        if ".git" in path.parts:
            continue
        output.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return output


def main() -> int:
    output_root = Path(os.environ.get("TASK25E_WRITE_OUTPUT_DIR", RUNTIME))
    if (output_root / "baseline.json").exists():
        raise SystemExit("Task 25E baseline already exists; refusing to overwrite immutable evidence")

    generated_at = now_iso()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at))
        if not user:
            user = db.scalar(select(User).where(User.status == "active").order_by(User.created_at))
        if not user:
            raise SystemExit("Task 25E baseline requires an active persisted user")

        service = RecordCenterService(db)
        engine = db.get_bind()
        with SQLTrace(engine) as trace:
            response = service.overview()

        search_pages = {}
        for page in (1, 2, 3):
            result = service.search(record_type="all", page=page, page_size=20)
            search_pages[str(page)] = {
                "total": result["total"],
                "record_ids_in_order": _ids(result["items"]),
            }

        filter_results = {}
        for record_type in sorted(RecordCenterService.ALLOWED_RECORD_TYPES - {"all"}):
            result = service.search(record_type=record_type, page=1, page_size=8)
            filter_results[record_type] = {
                "total": result["total"],
                "record_ids_in_order": _ids(result["items"]),
            }

        for _ in range(2):
            service.overview()
        latencies = []
        for _ in range(7):
            started = perf_counter()
            service.overview()
            latencies.append((perf_counter() - started) * 1000)

        counts = {
            name: int(db.scalar(select(func.count()).select_from(model)) or 0)
            for name, model in MODELS.items()
        }

    response_hash = sha256_value(response)
    task25d_report = ROOT / "docs" / "25D_maintenance_business_workflow_integration_report.md"
    task25d_runtime = ROOT / ".runtime" / "task25d" / "regression.json"
    git_status = run(["git", "status", "--short"], ROOT, timeout=60)
    heads = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"], BACKEND)
    current = run([sys.executable, "-m", "alembic", "-c", "alembic.ini", "current"], BACKEND)

    write_json("baseline_response.json", response)
    write_json(
        "baseline_response_hash.json",
        {
            "generated_at": generated_at,
            "algorithm": "SHA-256 over canonical sorted-key JSON",
            "sha256": response_hash,
            "recent_record_ids_in_order": _ids(response.get("recent_records", [])),
        },
    )
    write_json(
        "baseline_sql_trace.json",
        {
            "generated_at": generated_at,
            "request": {"method": "GET", "path": "/api/record-center/overview", "parameters": {}},
            "parameter_policy": "SQL parameters are never recorded",
            "statement_count": len(trace.statements),
            "statements": trace.statements,
        },
    )
    write_json(
        "baseline_sql_fingerprints.json",
        {
            "generated_at": generated_at,
            "statement_count": len(trace.statements),
            "unique_fingerprints": len(trace.fingerprints()),
            "top_30": trace.fingerprints(limit=30),
        },
    )
    baseline = {
        "generated_at": generated_at,
        "status": "TASK25E_BASELINE_FROZEN",
        "request": {"method": "GET", "path": "/api/record-center/overview", "parameters": {}},
        "principal": {"user_id": str(user.id), "role": user.role, "permission_scope": "existing_authenticated_record_center_scope"},
        "database_counts": counts,
        "response_sha256": response_hash,
        "overview_recent_record_ids_in_order": _ids(response.get("recent_records", [])),
        "overview_category_statistics": {key: value for key, value in response.items() if key != "recent_records"},
        "search_pages": search_pages,
        "filter_results": filter_results,
        "overview_sql_statements": len(trace.statements),
        "overview_unique_sql_fingerprints": len(trace.fingerprints()),
        "overview_latency": latency_summary(latencies),
        "alembic": {"heads": heads, "current": current},
        "backend_env_sha256": sha256_file(ROOT / "backend" / ".env"),
        "git_status": git_status,
        "zip_inventory": _zip_inventory(),
        "task25d_frozen_evidence": {
            "report_sha256": sha256_file(task25d_report),
            "regression_sha256": sha256_file(task25d_runtime),
        },
    }
    write_json("baseline.json", baseline)
    print(json.dumps({"status": baseline["status"], "sql": len(trace.statements), "latency": baseline["overview_latency"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
