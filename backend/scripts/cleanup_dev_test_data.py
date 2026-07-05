from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import (
    Device,
    DeviceMaintenanceRecord,
    DiagnosisRecord,
    KnowledgeChunk,
    KnowledgeContribution,
    KnowledgeDocument,
    KnowledgeReviewRecord,
    MaintenanceTask,
    ModelCallLog,
    ModelOutputCorrection,
    OperationLog,
    QARecord,
    SOPExecutionRecord,
    SOPTemplate,
    UploadedMedia,
    User,
)


PATTERNS = (
    "Task11A_Disposable",
    "Task14A_Smoke",
    "Task15",
    "Task16",
    "Task16A",
    "Task17B",
    "Task18B",
    "Task18I_",
    "Task21C_",
    "Task21D_",
    "probe",
    "permission probe",
    "verification",
    "??",
    "garbled_probe_marker",
)


@dataclass(slots=True)
class TableSpec:
    name: str
    model: type
    fields: tuple[str, ...]


TABLES: tuple[TableSpec, ...] = (
    TableSpec("users", User, ("username", "display_name", "role", "status")),
    TableSpec("operation_logs", OperationLog, ("module", "action", "target_type", "target_id", "operator", "request_id", "trace_id")),
    TableSpec("model_call_logs", ModelCallLog, ("trace_id", "module", "provider", "model_name", "prompt", "response", "error_message")),
    TableSpec("model_output_corrections", ModelOutputCorrection, ("source_type", "source_trace_id", "correction_reason", "review_status")),
    TableSpec("knowledge_review_records", KnowledgeReviewRecord, ("review_action", "review_comment", "before_status", "after_status")),
    TableSpec("knowledge_contributions", KnowledgeContribution, ("title", "content", "source_trace_id", "review_comment")),
    TableSpec("sop_execution_records", SOPExecutionRecord, ("abnormal_notes", "status")),
    TableSpec("sop_templates", SOPTemplate, ("title", "fault_type", "compliance_notes", "status")),
    TableSpec("uploaded_media", UploadedMedia, ("file_name", "original_file_name", "file_path", "description", "qa_trace_id", "status")),
    TableSpec("device_maintenance_records", DeviceMaintenanceRecord, ("diagnosis_trace_id", "qa_trace_id", "fault_description", "root_cause", "repair_action", "verification_result")),
    TableSpec("maintenance_tasks", MaintenanceTask, ("title", "device_name", "fault_description", "source_trace_id", "result_summary", "root_cause", "repair_action", "verification_result", "completion_notes")),
    TableSpec("diagnosis_records", DiagnosisRecord, ("device_name", "fault_type", "alarm_code", "alarm_info", "fault_description", "trace_id")),
    TableSpec("qa_records", QARecord, ("question", "normalized_query", "answer", "trace_id")),
    TableSpec("knowledge_chunks", KnowledgeChunk, ("content", "section_title")),
    TableSpec("knowledge_documents", KnowledgeDocument, ("title", "source", "file_name", "file_path", "summary", "error_message", "review_comment")),
    TableSpec("devices", Device, ("device_code", "device_name", "station_name", "location", "description")),
)


def stringify_values(row: object, fields: Iterable[str]) -> str:
    parts: list[str] = []
    for field in fields:
        value = getattr(row, field, None)
        if value is not None:
            parts.append(str(value))
    return "\n".join(parts)


def matches(row: object, fields: Iterable[str], patterns: Iterable[str]) -> bool:
    haystack = stringify_values(row, fields).lower()
    return any(pattern.lower() in haystack for pattern in patterns)


def main() -> int:
    parser = argparse.ArgumentParser(description="Identify or clean Energy-Maintenance development test data.")
    parser.add_argument("--execute", action="store_true", help="Soft-archive matched rows where safe. Default is dry-run only.")
    parser.add_argument(
        "--confirm",
        default="",
        help="Required with --execute. Use CLEAN_DEV_TEST_DATA to avoid accidental cleanup.",
    )
    parser.add_argument("--limit", type=int, default=5000, help="Maximum rows scanned per table.")
    parser.add_argument("--pattern", action="append", default=[], help="Additional marker pattern to match.")
    parser.add_argument(
        "--only-pattern",
        action="append",
        default=[],
        help="When provided, ignore default patterns and match only the given marker pattern.",
    )
    args = parser.parse_args()

    if args.execute and args.confirm != "CLEAN_DEV_TEST_DATA":
        print("--execute requires --confirm CLEAN_DEV_TEST_DATA")
        return 2

    patterns = tuple(args.only_pattern) if args.only_pattern else tuple(PATTERNS) + tuple(args.pattern)
    db = SessionLocal()
    total = 0
    matched_rows: list[tuple[TableSpec, object]] = []
    try:
        for spec in TABLES:
            rows = db.execute(select(spec.model).limit(args.limit)).scalars().all()
            matched = [
                row
                for row in rows
                if matches(row, spec.fields, patterns)
                and not is_retained_demo_row(row)
                and not is_already_cleaned(row)
            ]
            total += len(matched)
            matched_rows.extend((spec, row) for row in matched)
            print(f"{spec.name}: matched={len(matched)} scanned={len(rows)}")
            for row in matched[:20]:
                row_id = getattr(row, "id", "-")
                preview = stringify_values(row, spec.fields).replace("\n", " ")[:160]
                print(f"  - id={row_id} preview={preview}")
            if len(matched) > 20:
                print(f"  ... {len(matched) - 20} more")

        if not args.execute:
            print(f"Dry-run only. Matched rows: {total}. No data changed.")
            return 0

        changed = 0
        skipped = 0
        for spec, row in matched_rows:
            if soft_archive(row):
                changed += 1
            else:
                skipped += 1
                row_id = getattr(row, "id", "-")
                print(f"skip unsafe cleanup: table={spec.name} id={row_id}")
        db.commit()
        print(f"Soft-archived rows: {changed}; skipped rows: {skipped}; uploaded files were not removed.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def soft_archive(row: object) -> bool:
    if isinstance(row, User):
        row.status = "inactive"
        row.is_active = False
        return True
    if isinstance(row, MaintenanceTask):
        row.status = "cancelled"
        row.task_status = "cancelled"
        row.completion_notes = append_note(row.completion_notes, "Archived by cleanup_dev_test_data.py.")
        return True
    if isinstance(row, Device):
        row.status = "retired"
        row.description = append_note(row.description, "Retired by cleanup_dev_test_data.py.")
        return True
    if isinstance(row, DeviceMaintenanceRecord):
        return False
    if isinstance(row, (QARecord, DiagnosisRecord, ModelCallLog, OperationLog, KnowledgeReviewRecord)):
        return False
    if hasattr(row, "status"):
        setattr(row, "status", "archived")
        return True
    if hasattr(row, "review_status"):
        setattr(row, "review_status", "archived")
        return True
    return False


def is_retained_demo_row(row: object) -> bool:
    text_values: list[str] = []
    for field in (
        "title",
        "trace_id",
        "source_trace_id",
        "source",
        "source_type",
        "description",
        "metadata_json",
    ):
        value = getattr(row, field, None)
        if value is not None:
            text_values.append(str(value))
    haystack = "\n".join(text_values)
    return (
        "final_demo_seed" in haystack
        or "FINAL-DEMO" in haystack
        or haystack.startswith("Final Demo")
    )


def is_already_cleaned(row: object) -> bool:
    status = getattr(row, "status", None)
    review_status = getattr(row, "review_status", None)
    task_status = getattr(row, "task_status", None)
    if isinstance(row, User) and (status == "inactive" or getattr(row, "is_active", True) is False):
        return True
    if isinstance(row, Device) and status == "retired":
        return True
    if status == "archived" or review_status == "archived":
        return True
    if isinstance(row, MaintenanceTask) and (status == "cancelled" or task_status == "cancelled"):
        return True
    return False


def append_note(current: str | None, note: str) -> str:
    return f"{current}\n{note}" if current else note


if __name__ == "__main__":
    raise SystemExit(main())
