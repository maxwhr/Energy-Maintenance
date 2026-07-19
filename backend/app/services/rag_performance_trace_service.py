from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator


@dataclass(slots=True)
class RagPerformanceTrace:
    trace_id: str
    request_started_at: str
    request_finished_at: str | None = None
    total_ms: float | None = None
    query_hash: str | None = None
    scope_fingerprint: str | None = None
    mode: str | None = None
    cold_or_warm: str | None = None
    cache_status: str | None = None
    stages: dict[str, float | int | None] = field(default_factory=dict)
    sql_count: int | None = None
    sql_total_ms: float | None = None
    sql_wait_ms: float | None = None
    provider_request_count: int | None = None
    provider_total_ms: float | None = None
    provider_retry_count: int | None = None
    provider_timeout_count: int | None = None
    fallback_count: int | None = None


class RagPerformanceTraceService:
    """Best-effort request trace that stores hashes and metrics, never request text."""

    _current: ContextVar[RagPerformanceTrace | None] = ContextVar("rag_performance_trace", default=None)
    _recent: list[dict[str, Any]] = []
    _lock = threading.Lock()
    _capacity = 256

    @classmethod
    @contextmanager
    def trace(
        cls,
        *,
        trace_id: str,
        query: str,
        scope_fingerprint: str | None,
        mode: str,
        cold_or_warm: str | None = None,
        cache_status: str | None = None,
    ) -> Iterator[RagPerformanceTrace]:
        started = time.perf_counter()
        item = RagPerformanceTrace(
            trace_id=trace_id,
            request_started_at=datetime.now(timezone.utc).isoformat(),
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            scope_fingerprint=scope_fingerprint,
            mode=mode,
            cold_or_warm=cold_or_warm,
            cache_status=cache_status,
        )
        token = cls._current.set(item)
        try:
            yield item
        finally:
            item.request_finished_at = datetime.now(timezone.utc).isoformat()
            item.total_ms = round((time.perf_counter() - started) * 1000, 3)
            cls._current.reset(token)
            cls._remember(asdict(item))

    @classmethod
    @contextmanager
    def stage(cls, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            item = cls._current.get()
            if item is not None:
                item.stages[name] = round((time.perf_counter() - started) * 1000, 3)

    @classmethod
    def update_stages(cls, values: dict[str, float | int | None]) -> None:
        item = cls._current.get()
        if item is None:
            return
        for key, value in values.items():
            item.stages[key] = round(float(value), 3) if isinstance(value, (int, float)) else None

    @classmethod
    def current(cls) -> RagPerformanceTrace | None:
        return cls._current.get()

    @classmethod
    def recent(cls) -> list[dict[str, Any]]:
        with cls._lock:
            return list(cls._recent)

    @classmethod
    def _remember(cls, value: dict[str, Any]) -> None:
        try:
            with cls._lock:
                cls._recent.append(value)
                if len(cls._recent) > cls._capacity:
                    del cls._recent[: len(cls._recent) - cls._capacity]
        except Exception:
            # Trace failure must never fail retrieval.
            return
