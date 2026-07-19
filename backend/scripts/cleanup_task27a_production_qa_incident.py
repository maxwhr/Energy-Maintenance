from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import QARecord  # noqa: E402


INCIDENT_QUERY = "SUN2000-100KTL-M1 通信参数"


def extract_request_id(record: QARecord) -> str | None:
    for item in record.related_history or []:
        if isinstance(item, dict) and item.get("request_id"):
            return str(item["request_id"])
    return None


def _candidate_summary(record: QARecord) -> dict:
    return {
        "record_id": str(record.id),
        "trace_id": record.trace_id,
        "request_id": extract_request_id(record),
        "query": record.question,
        "created_at": record.created_at.isoformat(),
        "created_by": str(record.created_by) if record.created_by else None,
        "answer_length": len(record.answer or ""),
        "reference_count": len(record.references or []),
        "retrieved_chunk_count": len(record.retrieved_chunks or []),
    }


def _validate_apply_arguments(args: argparse.Namespace) -> None:
    missing = [
        name
        for name in ("authorized_by", "expected_record_id", "expected_trace_id", "expected_request_id")
        if not getattr(args, name)
    ]
    if missing:
        raise ValueError("--apply requires: " + ", ".join(f"--{name.replace('_', '-')}" for name in missing))
    if len(args.authorized_by.strip()) < 3:
        raise ValueError("--authorized-by must identify the human authorizer")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run-first cleanup for the single Task 27A production QA incident",
    )
    parser.add_argument("--database-name", required=True, help="Must exactly match the connected database name")
    parser.add_argument("--apply", action="store_true", help="Delete only after all exact guards pass")
    parser.add_argument("--authorized-by", help="Human authorizer identity; required with --apply")
    parser.add_argument("--expected-record-id", help="Exact UUID; required with --apply")
    parser.add_argument("--expected-trace-id", help="Exact trace ID; required with --apply")
    parser.add_argument("--expected-request-id", help="Exact request ID; required with --apply")
    args = parser.parse_args()

    connected_database = str(engine.url.database or "")
    if args.database_name != connected_database:
        parser.error("--database-name must exactly match the connected database")
    if args.apply:
        try:
            _validate_apply_arguments(args)
        except ValueError as exc:
            parser.error(str(exc))

    with SessionLocal() as db:
        count_before = int(db.scalar(select(func.count()).select_from(QARecord)) or 0)
        candidates = list(db.scalars(
            select(QARecord)
            .where(QARecord.question == INCIDENT_QUERY)
            .order_by(QARecord.created_at.desc())
        ))
        summaries = [_candidate_summary(record) for record in candidates]

        result = {
            "mode": "apply" if args.apply else "dry_run",
            "database_name": connected_database,
            "candidate_count": len(candidates),
            "count_before": count_before,
            "candidates": summaries,
            "cleanup_executed": False,
            "status": "PENDING_AUTHORIZED_CLEANUP",
        }

        if len(candidates) != 1:
            db.rollback()
            result["status"] = "REFUSED_NON_UNIQUE_MATCH"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2

        candidate = candidates[0]
        if not args.apply:
            db.rollback()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        exact_match = all((
            str(candidate.id) == args.expected_record_id,
            candidate.trace_id == args.expected_trace_id,
            extract_request_id(candidate) == args.expected_request_id,
            candidate.question == INCIDENT_QUERY,
        ))
        if not exact_match:
            db.rollback()
            result["status"] = "REFUSED_GUARD_MISMATCH"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2

        db.delete(candidate)
        db.flush()
        count_after = int(db.scalar(select(func.count()).select_from(QARecord)) or 0)
        if count_after != count_before - 1:
            db.rollback()
            result["status"] = "REFUSED_POST_DELETE_COUNT_MISMATCH"
            result["count_after_rollback"] = count_before
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        db.commit()
        result.update({
            "cleanup_executed": True,
            "status": "AUTHORIZED_CLEANUP_COMPLETED",
            "authorized_by": args.authorized_by,
            "count_after": count_after,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
