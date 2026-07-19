from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.models import QARecord, User  # noqa: E402


INCIDENT_QUERY = "SUN2000-100KTL-M1 通信参数"
SENSITIVE_KEY_PARTS = ("api_key", "authorization", "password", "secret", "access_token")


def _request_id(record: QARecord) -> str | None:
    for item in record.related_history or []:
        if isinstance(item, dict) and item.get("request_id"):
            return str(item["request_id"])
    return None


def _sensitive_keys(value: Any, *, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            normalized = str(key).casefold()
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                found.append(path)
            found.extend(_sensitive_keys(item, prefix=path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_sensitive_keys(item, prefix=f"{prefix}[{index}]"))
    return found


def _summary(record: QARecord, user: User | None) -> dict[str, Any]:
    sensitive_keys = sorted(set(_sensitive_keys({
        "references": record.references,
        "retrieved_chunks": record.retrieved_chunks,
        "related_history": record.related_history,
    })))
    return {
        "record_id": str(record.id),
        "trace_id": record.trace_id,
        "request_id": _request_id(record),
        "query": record.question,
        "created_at": record.created_at.isoformat(),
        "created_by": str(record.created_by) if record.created_by else None,
        "created_by_username": user.username if user else None,
        "answer_length": len(record.answer or ""),
        "reference_count": len(record.references or []),
        "retrieved_chunk_count": len(record.retrieved_chunks or []),
        "model_provider": record.model_provider,
        "model_name": record.model_name,
        "sensitive_key_names": sensitive_keys,
        "contains_detected_sensitive_keys": bool(sensitive_keys),
    }


def main() -> int:
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        rows = db.execute(
            select(QARecord, User)
            .outerjoin(User, QARecord.created_by == User.id)
            .where(QARecord.question == INCIDENT_QUERY)
            .order_by(QARecord.created_at.desc())
        ).all()
        summaries = [_summary(record, user) for record, user in rows]
        db.rollback()

    result = {
        "status": "IDENTIFIED" if len(summaries) == 1 else "REVIEW_REQUIRED",
        "mode": "read_only",
        "database": {
            "host": engine.url.host,
            "port": engine.url.port,
            "name": engine.url.database,
        },
        "candidate_count": len(summaries),
        "exactly_one_candidate": len(summaries) == 1,
        "records": summaries,
        "cleanup_executed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if len(summaries) == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
