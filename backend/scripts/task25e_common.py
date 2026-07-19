from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from sqlalchemy import event
from sqlalchemy.engine import Engine


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25e"
RUNTIME.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_default(value: Any) -> str:
    if isinstance(value, (datetime, Path)):
        return value.isoformat() if isinstance(value, datetime) else str(value)
    return str(value)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=json_default,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: str | Path, payload: Any) -> Path:
    target = Path(path)
    if not target.is_absolute():
        output_root = Path(os.environ.get("TASK25E_WRITE_OUTPUT_DIR", RUNTIME))
        target = output_root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    return target


def read_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.is_absolute():
        input_root = Path(os.environ.get("TASK25E_READ_INPUT_DIR", RUNTIME))
        target = input_root / target
    if not target.is_file():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def run(command: list[str], cwd: Path = ROOT, timeout: int = 120) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return round(ordered[low], 3)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (position - low), 3)


def latency_summary(values: list[float]) -> dict[str, Any]:
    return {
        "samples": len(values),
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "min_ms": round(min(values), 3) if values else 0.0,
        "max_ms": round(max(values), 3) if values else 0.0,
    }


_PARAMETER_PATTERNS = (
    (re.compile(r"%\([^)]+\)s"), "?"),
    (re.compile(r"\$\d+"), "?"),
    (re.compile(r"__\[POSTCOMPILE_[^\]]+\]"), "?"),
)


def sql_fingerprint(statement: str) -> str:
    normalized = " ".join(statement.strip().split())
    for pattern, replacement in _PARAMETER_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return normalized[:8000]


def _repository_context() -> tuple[str, str]:
    repository_method = "unknown"
    call_stack_category = "OTHER"
    for frame in reversed(traceback.extract_stack(limit=36)):
        path = frame.filename.replace("\\", "/")
        if path.endswith("record_center_repository.py"):
            repository_method = frame.name
            call_stack_category = "RECORD_CENTER_REPOSITORY"
            break
        if path.endswith("record_center_service.py"):
            repository_method = frame.name
            call_stack_category = "RECORD_CENTER_SERVICE"
    return repository_method, call_stack_category


def classify_sql(fingerprint: str, repository_method: str, relationship_load: bool) -> str:
    lowered = fingerprint.lower()
    if relationship_load:
        return "LAZY_RELATIONSHIP_LOAD"
    if " from users" in lowered:
        return "USER_N_PLUS_ONE" if repository_method in {"_item_from_record", "_media_payload"} else "OTHER"
    if " from devices" in lowered:
        return "DEVICE_N_PLUS_ONE" if repository_method in {"_device_for_record", "_item_from_record", "_media_payload"} else "OTHER"
    if " from maintenance_workflows" in lowered and repository_method in {"_item_from_record", "_related_records"}:
        return "WORKFLOW_N_PLUS_ONE"
    if " from diagnosis_records" in lowered and repository_method in {"_media_for_record", "_related_records"}:
        return "DIAGNOSIS_N_PLUS_ONE"
    if " from sop_" in lowered and repository_method == "_item_from_record":
        return "SOP_N_PLUS_ONE"
    if " from maintenance_tasks" in lowered and repository_method in {"_device_for_record", "_item_from_record"}:
        return "TASK_N_PLUS_ONE"
    if " from uploaded_media" in lowered and repository_method in {"_media_for_record", "_item_from_record"}:
        return "MEDIA_N_PLUS_ONE"
    if "correction" in lowered and repository_method.startswith("_"):
        return "CORRECTION_N_PLUS_ONE"
    if "operation_logs" in lowered and repository_method.startswith("_"):
        return "AUDIT_N_PLUS_ONE"
    if "count(" in lowered:
        return "REPEATED_COUNT_QUERY"
    if repository_method in {"_collect_items", "_items_for_type"}:
        return "PYTHON_SIDE_PAGINATION"
    return "OTHER"


class SQLTrace:
    """Collects statement metadata without parameters or sensitive values."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.statements: list[dict[str, Any]] = []
        self._active = False

    def __enter__(self) -> "SQLTrace":
        event.listen(self.engine, "before_cursor_execute", self._before)
        event.listen(self.engine, "after_cursor_execute", self._after)
        self._active = True
        return self

    def __exit__(self, *_args: Any) -> None:
        if self._active:
            event.remove(self.engine, "before_cursor_execute", self._before)
            event.remove(self.engine, "after_cursor_execute", self._after)
            self._active = False

    def _before(self, _conn: Any, _cursor: Any, statement: str, _parameters: Any, context: Any, _many: bool) -> None:
        repository_method, call_stack_category = _repository_context()
        context._task25e_started = perf_counter()
        context._task25e_repository_method = repository_method
        context._task25e_call_stack_category = call_stack_category

    def _after(self, _conn: Any, cursor: Any, statement: str, _parameters: Any, context: Any, _many: bool) -> None:
        elapsed_ms = (perf_counter() - getattr(context, "_task25e_started", perf_counter())) * 1000
        fingerprint = sql_fingerprint(statement)
        options = getattr(context, "execution_options", {}) or {}
        relationship_load = bool(options.get("_sa_orm_load_options")) and "relationship" in str(options.get("_sa_orm_load_options")).lower()
        repository_method = getattr(context, "_task25e_repository_method", "unknown")
        self.statements.append(
            {
                "sequence": len(self.statements) + 1,
                "statement_fingerprint": fingerprint,
                "duration_ms": round(elapsed_ms, 3),
                "row_count": cursor.rowcount if isinstance(cursor.rowcount, int) and cursor.rowcount >= 0 else None,
                "call_stack_category": getattr(context, "_task25e_call_stack_category", "OTHER"),
                "repository_method": repository_method,
                "relationship_load": relationship_load,
                "load_type": "relationship" if relationship_load else "direct",
                "category": classify_sql(fingerprint, repository_method, relationship_load),
            }
        )

    def fingerprints(self, limit: int | None = None) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in self.statements:
            groups[item["statement_fingerprint"]].append(item)
        output = []
        for fingerprint, rows in groups.items():
            durations = [float(row["duration_ms"]) for row in rows]
            categories = defaultdict(int)
            stack_categories = defaultdict(int)
            methods = defaultdict(int)
            for row in rows:
                categories[row["category"]] += 1
                stack_categories[row["call_stack_category"]] += 1
                methods[row["repository_method"]] += 1
            output.append(
                {
                    "statement_fingerprint": fingerprint,
                    "execution_count": len(rows),
                    "total_duration_ms": round(sum(durations), 3),
                    "average_duration_ms": round(sum(durations) / len(durations), 3),
                    "maximum_duration_ms": round(max(durations), 3),
                    "row_count": None,
                    "category": max(categories, key=categories.get),
                    "call_stack_category": max(stack_categories, key=stack_categories.get),
                    "repository_method": max(methods, key=methods.get),
                    "relationship_load": any(bool(row["relationship_load"]) for row in rows),
                    "load_type": "relationship" if any(bool(row["relationship_load"]) for row in rows) else "direct",
                }
            )
        output.sort(key=lambda row: (-int(row["execution_count"]), -float(row["total_duration_ms"])))
        return output[:limit] if limit else output
