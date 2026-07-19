from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import threading
import traceback
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from unittest.mock import patch

from sqlalchemy import event, select
from sqlalchemy.engine import Engine

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
RUNTIME = ROOT / ".runtime" / "task25f"
SOURCE_DATASET = ROOT / ".runtime" / "task25b_r3_dev_r5_r5" / "train_dev_dataset_v1.json"
SUITE_VERSION = "task25f_rag_performance_suite_v1"
RUNTIME.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    if not target.is_file():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any, *, overwrite: bool = True) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    if target.exists() and not overwrite:
        raise RuntimeError(f"refusing to overwrite immutable Task 25F evidence: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )
    return target


def write_csv(path: str | Path, rows: list[dict[str, Any]], fields: list[str]) -> Path:
    import csv

    target = Path(path)
    if not target.is_absolute():
        target = RUNTIME / target
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rows)
    return target


def run(command: list[str], cwd: Path = ROOT, timeout: int = 300) -> dict[str, Any]:
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


def _sql_context() -> tuple[str, str, bool]:
    repository_method = "unknown"
    stage = "OTHER"
    serializer = False
    for frame in reversed(traceback.extract_stack(limit=48)):
        path = frame.filename.replace("\\", "/")
        if "pydantic/" in path or frame.name in {"model_dump", "serialize"}:
            serializer = True
        if path.endswith("retrieval_repository.py"):
            repository_method = frame.name
            stage = "KEYWORD_OR_SCOPE"
            break
        if path.endswith("semantic_anchor_repository.py"):
            repository_method = frame.name
            stage = "SEMANTIC_UNIT"
            break
        if path.endswith("citation_validation_service.py"):
            repository_method = frame.name
            stage = "CITATION"
            break
        if path.endswith("retrieval_scope_service.py"):
            repository_method = frame.name
            stage = "SCOPE_RESOLUTION"
            break
        if path.endswith("vector_index_repository.py"):
            repository_method = frame.name
            stage = "VECTOR_HYDRATION"
            break
    return repository_method, stage, serializer


def classify_sql(fingerprint: str, repository_method: str, stage: str, relationship: bool, serializer: bool) -> str:
    lowered = fingerprint.lower()
    if serializer:
        return "SERIALIZER_TRIGGERED_SQL"
    if relationship:
        if "knowledge_documents" in lowered:
            return "DOCUMENT_N_PLUS_ONE"
        if "knowledge_chunks" in lowered:
            return "CHUNK_N_PLUS_ONE"
        return "OTHER"
    if stage == "CITATION" and "knowledge_chunks" in lowered:
        return "CITATION_N_PLUS_ONE" if repository_method not in {"validate", "validate_candidates"} else "OTHER"
    if stage == "SCOPE_RESOLUTION":
        # A single scope-resolution statement is expected.  Repeat detection
        # is performed per request by the SQL audit, not from the stage name.
        return "OTHER"
    if "semantic_anchors" in lowered and repository_method not in {"by_vector_ids"}:
        return "SEMANTIC_UNIT_N_PLUS_ONE"
    if "knowledge_documents" in lowered and "knowledge_chunks" not in lowered and " in (" not in lowered:
        return "DOCUMENT_N_PLUS_ONE"
    if "count(" in lowered:
        return "REPEATED_COUNT_QUERY"
    return "OTHER"


class SQLTrace:
    """Thread-safe, parameter-free SQL trace for the complete RAG request."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.statements: list[dict[str, Any]] = []
        self.pool_wait_ms: list[float] = []
        self._checkout_started: dict[int, float] = {}
        self._lock = threading.Lock()
        self._active = False

    def __enter__(self) -> "SQLTrace":
        event.listen(self.engine, "before_cursor_execute", self._before)
        event.listen(self.engine, "after_cursor_execute", self._after)
        event.listen(self.engine, "checkout", self._checkout)
        self._active = True
        return self

    def __exit__(self, *_args: Any) -> None:
        if not self._active:
            return
        event.remove(self.engine, "before_cursor_execute", self._before)
        event.remove(self.engine, "after_cursor_execute", self._after)
        event.remove(self.engine, "checkout", self._checkout)
        self._active = False

    def _checkout(self, _dbapi_connection: Any, connection_record: Any, _connection_proxy: Any) -> None:
        # SQLAlchemy does not expose queue entry time here. This records checkout hook
        # overhead as an explicit nullable proxy, never a fabricated pool wait value.
        started = self._checkout_started.pop(id(connection_record), None)
        if started is not None:
            with self._lock:
                self.pool_wait_ms.append((perf_counter() - started) * 1000)

    def _before(self, _conn: Any, _cursor: Any, _statement: str, _parameters: Any, context: Any, _many: bool) -> None:
        repository_method, stage, serializer = _sql_context()
        context._task25f_started = perf_counter()
        context._task25f_repository_method = repository_method
        context._task25f_stage = stage
        context._task25f_serializer = serializer

    def _after(self, _conn: Any, cursor: Any, statement: str, _parameters: Any, context: Any, _many: bool) -> None:
        elapsed_ms = (perf_counter() - getattr(context, "_task25f_started", perf_counter())) * 1000
        fingerprint = sql_fingerprint(statement)
        options = getattr(context, "execution_options", {}) or {}
        relationship = bool(options.get("_sa_orm_load_options")) and "relationship" in str(options.get("_sa_orm_load_options")).lower()
        repository_method = getattr(context, "_task25f_repository_method", "unknown")
        stage = getattr(context, "_task25f_stage", "OTHER")
        serializer = bool(getattr(context, "_task25f_serializer", False))
        item = {
            "statement_fingerprint": fingerprint,
            "duration_ms": round(elapsed_ms, 3),
            "row_count": cursor.rowcount if isinstance(cursor.rowcount, int) and cursor.rowcount >= 0 else None,
            "repository_method": repository_method,
            "stage": stage,
            "lazy_load": relationship,
            "serializer_triggered": serializer,
            "category": classify_sql(fingerprint, repository_method, stage, relationship, serializer),
        }
        with self._lock:
            item["sequence"] = len(self.statements) + 1
            self.statements.append(item)

    def fingerprints(self, limit: int | None = None) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in self.statements:
            groups[item["statement_fingerprint"]].append(item)
        output: list[dict[str, Any]] = []
        for fingerprint, rows in groups.items():
            durations = [float(row["duration_ms"]) for row in rows]
            categories = Counter(row["category"] for row in rows)
            stages = Counter(row["stage"] for row in rows)
            methods = Counter(row["repository_method"] for row in rows)
            output.append({
                "statement_fingerprint": fingerprint,
                "execution_count": len(rows),
                "total_duration_ms": round(sum(durations), 3),
                "average_duration_ms": round(sum(durations) / len(durations), 3),
                "maximum_duration_ms": round(max(durations), 3),
                "row_count": sum(row["row_count"] or 0 for row in rows),
                "repository_method": methods.most_common(1)[0][0],
                "stage": stages.most_common(1)[0][0],
                "lazy_load": any(bool(row["lazy_load"]) for row in rows),
                "serializer_triggered": any(bool(row["serializer_triggered"]) for row in rows),
                "duplicate_query_group": len(rows) > 1,
                "category": categories.most_common(1)[0][0],
            })
        output.sort(key=lambda row: (-int(row["execution_count"]), -float(row["total_duration_ms"])))
        return output[:limit] if limit else output


class ProviderTrace:
    """Counts real provider method calls without retaining payloads or vectors."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._active = 0
        self.max_concurrent = 0
        self._stack = ExitStack()

    def __enter__(self) -> "ProviderTrace":
        from app.services.embedding_service import EmbeddingService
        from app.services.vector_store_adapters.dashvector_adapter import DashVectorAdapter

        original_embed = EmbeddingService.embed_texts
        original_vector = DashVectorAdapter.query_vectors

        def embed_wrapper(instance: Any, texts: list[str], *, provider: str | None = None):
            return self._call(
                "dashscope", "embedding", getattr(instance.settings, "EMBEDDING_MODEL", None),
                lambda: original_embed(instance, texts, provider=provider),
            )

        def vector_wrapper(
            instance: Any,
            *,
            vector: list[float],
            top_k: int,
            filters: dict | None = None,
            request_context: dict | None = None,
        ):
            operation = "semantic_unit" if (filters or {}).get("object_type") == "maintenance_semantic_unit" else "raw_vector"
            return self._call(
                "dashvector", operation, getattr(instance, "collection_name", None),
                lambda: original_vector(
                    instance,
                    vector=vector,
                    top_k=top_k,
                    filters=filters,
                    request_context=request_context,
                ),
                instance=instance,
            )

        self._stack.enter_context(patch.object(EmbeddingService, "embed_texts", embed_wrapper))
        self._stack.enter_context(patch.object(DashVectorAdapter, "query_vectors", vector_wrapper))
        return self

    def __exit__(self, *args: Any) -> None:
        self._stack.close()

    def _call(
        self,
        provider: str,
        operation: str,
        model: str | None,
        callback: Callable[[], Any],
        *,
        instance: Any | None = None,
    ) -> Any:
        with self._lock:
            self._active += 1
            self.max_concurrent = max(self.max_concurrent, self._active)
        started = perf_counter()
        error: Exception | None = None
        try:
            return callback()
        except Exception as exc:  # noqa: BLE001 - telemetry re-raises unchanged.
            error = exc
            raise
        finally:
            elapsed = (perf_counter() - started) * 1000
            with self._lock:
                self._active -= 1
                self.calls.append({
                    "provider": provider,
                    "operation": operation,
                    "model": model,
                    "endpoint_hash": None,
                    "latency_ms": round(elapsed, 3),
                    "success": error is None,
                    "failure": type(error).__name__ if error else None,
                    "retry_count": int(getattr(instance, "last_retries", 0) or 0),
                    "timeout": bool(error and "timeout" in type(error).__name__.lower()),
                    "http_429": bool(error and "429" in str(error)),
                    "http_5xx": bool(error and re.search(r"\b5\d\d\b", str(error))),
                })

    def summary(self) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str, str | None], list[dict[str, Any]]] = defaultdict(list)
        for row in self.calls:
            groups[(row["provider"], row["operation"], row["model"])].append(row)
        output = []
        for (provider, operation, model), rows in sorted(groups.items()):
            latencies = [float(row["latency_ms"]) for row in rows]
            output.append({
                "provider": provider,
                "operation": operation,
                "model": model,
                "endpoint_hash": None,
                "request_count": len(rows),
                "success_count": sum(bool(row["success"]) for row in rows),
                "failure_count": sum(not bool(row["success"]) for row in rows),
                "retry_count": sum(int(row["retry_count"]) for row in rows),
                "timeout_count": sum(bool(row["timeout"]) for row in rows),
                "429_count": sum(bool(row["http_429"]) for row in rows),
                "5xx_count": sum(bool(row["http_5xx"]) for row in rows),
                "p50_ms": percentile(latencies, 0.50),
                "p95_ms": percentile(latencies, 0.95),
                "max_ms": round(max(latencies), 3) if latencies else 0.0,
                "concurrent_requests": self.max_concurrent,
            })
        return output


def performance_tags(row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    mapping = {
        "exact_model": bool(row.get("expected_device_models")),
        "exact_alarm": bool(row.get("expected_alarm_codes")),
        "oral": bool(row.get("oral")),
        "communication": bool(row.get("communication")),
        "action": bool(row.get("action")) or "ACTION" in (row.get("expected_requested_information") or []),
        "cause": bool(row.get("cause")) or "CAUSE" in (row.get("expected_requested_information") or []),
        "safety": bool(row.get("safety")) or "SAFETY" in (row.get("expected_requested_information") or []),
        "prerequisite": "PREREQUISITE" in (row.get("expected_requested_information") or []),
        "verification": bool(row.get("verification")) or "VERIFICATION" in (row.get("expected_requested_information") or []),
        "composite_intent": bool(row.get("composite_intent")),
        "no_answer": bool(row.get("no_answer")),
        "requires_clarification": bool(row.get("requires_clarification")),
        "multi_query": bool(row.get("composite_intent") or row.get("oral") or row.get("vector_heavy")),
        "raw_vector": bool(row.get("vector_heavy")),
        "semantic_unit": bool(row.get("vector_heavy")),
        "html_faq": bool(row.get("html_faq")),
        "pdf": bool(row.get("pdf")),
    }
    for key, enabled in mapping.items():
        if enabled:
            tags.append(key)
    return tags


SUITE_REQUIREMENTS = {
    "exact_model": 8,
    "exact_alarm": 8,
    "oral": 8,
    "communication": 6,
    "action": 6,
    "cause": 6,
    "safety": 5,
    "prerequisite": 5,
    "verification": 5,
    "composite_intent": 8,
    "no_answer": 5,
    "requires_clarification": 5,
    "multi_query": 10,
    "raw_vector": 10,
    "semantic_unit": 10,
    "html_faq": 5,
    "pdf": 10,
}


def build_performance_suite(case_count: int = 60) -> dict[str, Any]:
    source = json.loads(SOURCE_DATASET.read_text(encoding="utf-8"))
    rows = list(source.get("rows") or [])
    tagged = [(row, performance_tags(row)) for row in rows]
    selected: list[tuple[dict[str, Any], list[str]]] = []
    selected_ids: set[str] = set()
    counts: Counter[str] = Counter()

    while len(selected) < min(case_count, len(tagged)):
        best: tuple[dict[str, Any], list[str]] | None = None
        best_score = -1
        for row, tags in tagged:
            case_id = str(row.get("case_id"))
            if case_id in selected_ids:
                continue
            score = sum(max(0, SUITE_REQUIREMENTS[tag] - counts[tag]) for tag in tags if tag in SUITE_REQUIREMENTS)
            if score > best_score:
                best = (row, tags)
                best_score = score
        if best is None:
            break
        row, tags = best
        selected.append(best)
        selected_ids.add(str(row.get("case_id")))
        counts.update(tags)

    suite_rows = []
    for index, (row, tags) in enumerate(selected, start=1):
        query = str(row.get("query") or "").strip()
        suite_rows.append({
            "ordinal": index,
            "source_case_id": row.get("case_id"),
            "source_dataset_version": row.get("dataset_version"),
            "query": query,
            "query_hash": sha256_text(query),
            "tags": tags,
            "expected_result_hash": sha256_value({
                "chunk_ids": row.get("expected_chunk_ids") or [],
                "semantic_unit_ids": row.get("expected_semantic_unit_ids") or [],
                "document_ids": row.get("expected_document_ids") or [],
            }),
            "expected_citation_hash": sha256_value({
                "chunk_ids": row.get("expected_chunk_ids") or [],
                "source_locators": row.get("source_locators") or [row.get("source_locator")],
            }),
            "expected_no_answer": bool(row.get("no_answer")),
            "expected_clarification": bool(row.get("requires_clarification")),
        })
    manifest_without_hash = {
        "generated_at": now_iso(),
        "dataset_version": SUITE_VERSION,
        "source_dataset": SOURCE_DATASET.relative_to(ROOT).as_posix(),
        "source_dataset_sha256": sha256_file(SOURCE_DATASET),
        "source_formal_test_used": False,
        "case_count": len(suite_rows),
        "coverage": dict(sorted(Counter(tag for row in suite_rows for tag in row["tags"]).items())),
        "requirements": SUITE_REQUIREMENTS,
        "requirements_passed": all(counts[key] >= value for key, value in SUITE_REQUIREMENTS.items()),
        "rows": suite_rows,
    }
    manifest_without_hash["dataset_sha256"] = sha256_value({
        "dataset_version": SUITE_VERSION,
        "rows": suite_rows,
    })
    return manifest_without_hash


def load_suite() -> dict[str, Any]:
    suite = read_json("performance_suite_manifest.json")
    if not suite:
        suite = build_performance_suite()
        write_json("performance_suite_manifest.json", suite, overwrite=False)
    return suite


def result_projection(response: Any) -> dict[str, Any]:
    value = response.model_dump(mode="json") if hasattr(response, "model_dump") else dict(response)
    raw = value.get("raw_results") or []
    surfaced = value.get("surfaced_results") or []
    citations = value.get("citations") or []
    diagnostics = value.get("diagnostics") or {}
    return {
        "query_understanding": {
            "normalized_query": value.get("normalized_query"),
            "canonical_question": value.get("canonical_question"),
            "primary_intent": value.get("primary_intent"),
            "requested_information": value.get("requested_information") or [],
            "mode": value.get("query_understanding_mode"),
        },
        "query_variants": value.get("generated_queries") or [],
        "requested_channels": value.get("requested_channels") or [],
        "actual_channels": value.get("actual_channels") or [],
        "candidate_identities": [item.get("candidate_id") for item in raw],
        "top5_identities": [item.get("candidate_id") for item in surfaced[:5]],
        "top10_identities": [item.get("candidate_id") for item in surfaced[:10]],
        "citation_identities": [item.get("chunk_id") for item in citations],
        "citation_locators": [item.get("source_locator") for item in citations],
        "confidence_status": value.get("confidence_status"),
        "needs_clarification": bool(value.get("needs_clarification")),
        "no_answer": value.get("confidence_status") == "INSUFFICIENT_EVIDENCE",
        "candidate_channel_counts": value.get("candidate_channel_counts") or {},
        "stage_latency": value.get("stage_latency") or {},
        "scope_leakage": not bool((diagnostics.get("scope_validation_passed", True))),
        "quality_status": value.get("quality_status"),
    }


def run_case(case: dict[str, Any], *, allow_real_api: bool, cache_mode: str = "off") -> dict[str, Any]:
    from app.core.database import SessionLocal, engine
    from app.models import User
    from app.schemas.query_aware_retrieval import QueryAwareSearchRequest
    from app.services.embedding_service import EmbeddingService
    from app.services.query_aware_retrieval_service import QueryAwareRetrievalService

    if cache_mode == "off":
        with EmbeddingService._cache_lock:
            EmbeddingService._query_cache.clear()
    with SessionLocal() as auth_db:
        user = auth_db.scalar(
            select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at)
        )
        if user is None:
            user = auth_db.scalar(select(User).where(User.status == "active").order_by(User.created_at))
        if user is None:
            raise RuntimeError("Task 25F requires an active persisted user")
        user_id = user.id
    with SessionLocal() as db, SQLTrace(engine) as sql_trace, ProviderTrace() as provider_trace:
        started = perf_counter()
        service = QueryAwareRetrievalService(db, current_user=db.get(User, user_id))
        response = service.search(QueryAwareSearchRequest(
            query=case["query"],
            retrieval_mode="auto",
            top_k=10,
            enable_llm=True,
            allow_real_api=allow_real_api,
        ))
        projection = result_projection(response)
        # Include Pydantic serialization in the SQL trace to prove serializer SQL=0.
        response.model_dump(mode="json")
        total_ms = (perf_counter() - started) * 1000
    sql_total = sum(float(item["duration_ms"]) for item in sql_trace.statements)
    provider_total = sum(float(item["latency_ms"]) for item in provider_trace.calls)
    return {
        "source_case_id": case["source_case_id"],
        "query_hash": case["query_hash"],
        "tags": case.get("tags") or [],
        "cache_mode": cache_mode,
        "total_ms": round(total_ms, 3),
        "result": projection,
        "result_hash": sha256_value(projection),
        "citation_hash": sha256_value({
            "identities": projection["citation_identities"],
            "locators": projection["citation_locators"],
        }),
        "sql": {
            "count": len(sql_trace.statements),
            "total_ms": round(sql_total, 3),
            "wait_ms": None,
            "serializer_sql": sum(bool(item["serializer_triggered"]) for item in sql_trace.statements),
            "n_plus_one_warnings": sum(
                item["category"].endswith("N_PLUS_ONE") for item in sql_trace.fingerprints()
            ),
            "statements": sql_trace.statements,
            "fingerprints": sql_trace.fingerprints(limit=30),
        },
        "provider": {
            "request_count": len(provider_trace.calls),
            "total_ms": round(provider_total, 3),
            "max_concurrent": provider_trace.max_concurrent,
            "calls": provider_trace.calls,
            "summary": provider_trace.summary(),
        },
    }


def aggregate_case_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(cases),
        "total_latency": latency_summary([float(item["total_ms"]) for item in cases]),
        "sql_count": latency_summary([float(item["sql"]["count"]) for item in cases]),
        "sql_total": latency_summary([float(item["sql"]["total_ms"]) for item in cases]),
        "provider_requests": latency_summary([float(item["provider"]["request_count"]) for item in cases]),
        "provider_total": latency_summary([float(item["provider"]["total_ms"]) for item in cases]),
        "error_count": sum(bool(item.get("error")) for item in cases),
        "timeout_count": sum("timeout" in str(item.get("error") or "").lower() for item in cases),
        "serializer_sql": sum(int(item["sql"]["serializer_sql"]) for item in cases if "sql" in item),
        "n_plus_one_warnings": sum(int(item["sql"]["n_plus_one_warnings"]) for item in cases if "sql" in item),
    }
