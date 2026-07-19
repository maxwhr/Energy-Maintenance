from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Generic, TypeVar


T = TypeVar("T")


class TTLCache(Generic[T]):
    """Small process-local TTL/LRU cache that never persists prompts or provider secrets."""

    def __init__(self, *, max_entries: int, ttl_seconds: float) -> None:
        self.max_entries = max(1, int(max_entries))
        self.ttl_seconds = max(0.001, float(ttl_seconds))
        self._values: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        now = time.monotonic()
        with self._lock:
            item = self._values.pop(key, None)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                return None
            self._values[key] = item
            return deepcopy(value)

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._values.pop(key, None)
            self._values[key] = (time.monotonic() + self.ttl_seconds, deepcopy(value))
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._values)


@dataclass(slots=True)
class _BreakerChannel:
    state: str = "CLOSED"
    outcomes: deque[tuple[bool, str, float]] = field(default_factory=lambda: deque(maxlen=10))
    consecutive_5xx: int = 0
    consecutive_transport_errors: int = 0
    consecutive_no_tool_use: int = 0
    schema_validation_failures: int = 0
    opened_at: float | None = None
    half_open_probe_in_flight: bool = False


class MiniMaxCircuitBreaker:
    """Independent query-understanding and tie-break circuit states."""

    CHANNELS = ("query_understanding", "tiebreak")

    def __init__(self, *, cooldown_seconds: float = 60.0) -> None:
        self.cooldown_seconds = max(1.0, float(cooldown_seconds))
        self._channels = {name: _BreakerChannel() for name in self.CHANNELS}
        self._lock = threading.Lock()

    def allow(self, channel: str) -> bool:
        with self._lock:
            item = self._get(channel)
            if item.state == "CLOSED":
                return True
            if item.state == "OPEN":
                if item.opened_at is None or time.monotonic() - item.opened_at < self.cooldown_seconds:
                    return False
                item.state = "HALF_OPEN"
                item.half_open_probe_in_flight = False
            if item.half_open_probe_in_flight:
                return False
            item.half_open_probe_in_flight = True
            return True

    def record(
        self,
        channel: str,
        *,
        success: bool,
        error_code: str | None = None,
        latency_ms: float = 0.0,
        probe_mode: bool = False,
    ) -> None:
        code = (error_code or "").upper()
        with self._lock:
            item = self._get(channel)
            item.outcomes.append((success, code, max(0.0, float(latency_ms))))
            item.half_open_probe_in_flight = False
            if success:
                item.consecutive_5xx = 0
                item.consecutive_transport_errors = 0
                item.consecutive_no_tool_use = 0
                if item.state == "HALF_OPEN":
                    item.state = "CLOSED"
                    item.opened_at = None
                    item.outcomes.clear()
                return
            if code == "SCHEMA_VALIDATION_FAILED":
                item.schema_validation_failures += 1
            item.consecutive_5xx = item.consecutive_5xx + 1 if code.startswith("HTTP_5") else 0
            item.consecutive_transport_errors = (
                item.consecutive_transport_errors + 1
                if code in {"PROVIDER_UNAVAILABLE", "CONNECTION_RESET", "CONNECTION_REFUSED"}
                else 0
            )
            item.consecutive_no_tool_use = item.consecutive_no_tool_use + 1 if code == "NO_TOOL_USE" else 0
            if probe_mode:
                return
            recent_five = list(item.outcomes)[-5:]
            timeout_trip = len(recent_five) >= 5 and sum(code_ == "TIMEOUT" for ok, code_, _ in recent_five if not ok) >= 3
            if (
                item.state == "HALF_OPEN"
                or timeout_trip
                or item.consecutive_5xx >= 3
                or item.consecutive_transport_errors >= 3
                or item.consecutive_no_tool_use >= 5
            ):
                item.state = "OPEN"
                item.opened_at = time.monotonic()

    def state(self, channel: str) -> str:
        with self._lock:
            return self._get(channel).state

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            return {
                name: {
                    "state": item.state,
                    "recent_calls": len(item.outcomes),
                    "consecutive_5xx": item.consecutive_5xx,
                    "consecutive_transport_errors": item.consecutive_transport_errors,
                    "consecutive_no_tool_use": item.consecutive_no_tool_use,
                    "schema_validation_failures": item.schema_validation_failures,
                    "half_open_probe_in_flight": item.half_open_probe_in_flight,
                }
                for name, item in self._channels.items()
            }

    def reset(self, channel: str | None = None) -> None:
        with self._lock:
            names = [channel] if channel else list(self.CHANNELS)
            for name in names:
                self._channels[name] = _BreakerChannel()

    def _get(self, channel: str) -> _BreakerChannel:
        if channel not in self._channels:
            raise ValueError(f"unsupported MiniMax circuit channel: {channel}")
        return self._channels[channel]


_shared_breaker: MiniMaxCircuitBreaker | None = None
_shared_lock = threading.Lock()


def get_minimax_circuit_breaker(*, cooldown_seconds: float = 60.0) -> MiniMaxCircuitBreaker:
    global _shared_breaker
    with _shared_lock:
        if _shared_breaker is None:
            _shared_breaker = MiniMaxCircuitBreaker(cooldown_seconds=cooldown_seconds)
        return _shared_breaker
